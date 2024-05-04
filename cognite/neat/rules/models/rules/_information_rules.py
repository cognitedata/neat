import math
import re
import sys
import warnings
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from pydantic import Field, field_serializer, field_validator, model_serializer, model_validator
from pydantic_core.core_schema import SerializationInfo
from rdflib import Namespace

import cognite.neat.rules.issues.spreadsheet
from cognite.neat.constants import PREFIXES
from cognite.neat.rules import exceptions
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    Entity,
    EntityTypes,
    ParentClassEntity,
    ParentEntityList,
    ReferenceEntity,
    Undefined,
    Unknown,
    UnknownEntity,
    URLEntity,
    ViewEntity,
    ViewPropertyEntity,
    _UndefinedType,
    _UnknownType,
)
from cognite.neat.rules.models.rdfpath import (
    AllReferences,
    Hop,
    RawLookup,
    SingleProperty,
    SPARQLQuery,
    TransformationRuleType,
    Traversal,
    parse_rule,
)

from ._base import (
    BaseMetadata,
    ExtensionCategory,
    ExtensionCategoryType,
    MatchType,
    RoleTypes,
    RuleModel,
    SchemaCompleteness,
    SheetEntity,
    SheetList,
)
from ._domain_rules import DomainRules
from ._types import (
    NamespaceType,
    PrefixType,
    PropertyType,
    StrListType,
    VersionType,
)

if TYPE_CHECKING:
    from ._dms_architect_rules import DMSProperty, DMSRules


if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class InformationMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.information_architect
    schema_: SchemaCompleteness = Field(alias="schema")
    extension: ExtensionCategoryType | None = ExtensionCategory.addition
    prefix: PrefixType
    namespace: NamespaceType

    name: str = Field(
        alias="title",
        description="Human readable name of the data model",
        min_length=1,
        max_length=255,
    )
    description: str | None = Field(None, min_length=1, max_length=1024)
    version: VersionType

    created: datetime = Field(
        description=("Date of the data model creation"),
    )

    updated: datetime = Field(
        description=("Date of the data model update"),
    )
    creator: StrListType = Field(
        description=(
            "List of contributors to the data model creation, "
            "typically information architects are considered as contributors."
        ),
    )

    @model_validator(mode="after")
    def extension_none_but_schema_extend(self) -> Self:
        if self.extension is None:
            self.extension = ExtensionCategory.addition
            return self
        return self


class InformationClass(SheetEntity):
    """
    Class is a category of things that share a common set of attributes and relationships.

    Args:
        class_: The class ID of the class.
        description: A description of the class.
        parent: The parent class of the class.
        reference: Reference of the source of the information for given resource
        match_type: The match type of the resource being described and the source entity.
    """

    parent: ParentEntityList | None = Field(alias="Parent Class", default=None)
    reference: URLEntity | ReferenceEntity | None = Field(alias="Reference", default=None, union_mode="left_to_right")
    match_type: MatchType | None = Field(alias="Match Type", default=None)
    comment: str | None = Field(alias="Comment", default=None)


class InformationProperty(SheetEntity):
    """
    A property is a characteristic of a class. It is a named attribute of a class that describes a range of values
    or a relationship to another class.

    Args:
        class_: Class ID to which property belongs
        property_: Property ID of the property
        name: Property name.
        value_type: Type of value property will hold (data or link to another class)
        min_count: Minimum count of the property values. Defaults to 0
        max_count: Maximum count of the property values. Defaults to None
        default: Default value of the property
        reference: Reference to the source of the information, HTTP URI
        match_type: The match type of the resource being described and the source entity.
        rule_type: Rule type for the transformation from source to target representation
                   of knowledge graph. Defaults to None (no transformation)
        rule: Actual rule for the transformation from source to target representation of
              knowledge graph. Defaults to None (no transformation)
    """

    property_: PropertyType = Field(alias="Property")
    value_type: DataType | ClassEntity | UnknownEntity = Field(alias="Value Type", union_mode="left_to_right")
    min_count: int | None = Field(alias="Min Count", default=None)
    max_count: int | float | None = Field(alias="Max Count", default=None)
    default: Any | None = Field(alias="Default", default=None)
    reference: URLEntity | ReferenceEntity | None = Field(alias="Reference", default=None, union_mode="left_to_right")
    match_type: MatchType | None = Field(alias="Match Type", default=None)
    rule_type: str | TransformationRuleType | None = Field(alias="Rule Type", default=None)
    rule: str | AllReferences | SingleProperty | Hop | RawLookup | SPARQLQuery | Traversal | None = Field(
        alias="Rule", default=None
    )
    comment: str | None = Field(alias="Comment", default=None)

    @field_serializer("max_count", when_used="json-unless-none")
    def serialize_max_count(self, value: int | float | None) -> int | float | None | str:
        if isinstance(value, float) and math.isinf(value):
            return None
        return value

    @field_validator("max_count", mode="before")
    def parse_max_count(cls, value: int | float | None) -> int | float | None:
        if value is None:
            return float("inf")
        return value

    @model_validator(mode="after")
    def is_valid_rule(self):
        # TODO: Can we skip rule_type and simply try to parse the rule and if it fails, raise an error?
        if self.rule_type:
            self.rule_type = self.rule_type.lower()
            if not self.rule:
                raise exceptions.RuleTypeProvidedButRuleMissing(
                    self.property_, self.class_, self.rule_type
                ).to_pydantic_custom_error()
            self.rule = parse_rule(self.rule, self.rule_type)
        return self

    @model_validator(mode="after")
    def set_default_as_list(self):
        if (
            self.type_ == EntityTypes.data_property
            and self.default
            and self.is_list
            and not isinstance(self.default, list)
        ):
            if isinstance(self.default, str):
                if self.default:
                    self.default = self.default.replace(", ", ",").split(",")
                else:
                    self.default = [self.default]
        return self

    @model_validator(mode="after")
    def set_type_for_default(self):
        if self.type_ == EntityTypes.data_property and self.default:
            default_value = self.default[0] if isinstance(self.default, list) else self.default

            if type(default_value) != self.value_type.python:
                try:
                    if isinstance(self.default, list):
                        updated_list = []
                        for value in self.default:
                            updated_list.append(self.value_type.python(value))
                        self.default = updated_list
                    else:
                        self.default = self.value_type.python(self.default)

                except Exception:
                    exceptions.DefaultValueTypeNotProper(
                        self.property_,
                        type(self.default),
                        self.value_type.python,
                    )
        return self

    @property
    def type_(self) -> EntityTypes:
        """Type of property based on value type. Either data (attribute) or object (edge) property."""
        if isinstance(self.value_type, DataType):
            return EntityTypes.data_property
        elif isinstance(self.value_type, ClassEntity):
            return EntityTypes.object_property
        else:
            return EntityTypes.undefined

    @property
    def is_mandatory(self) -> bool:
        """Returns True if property is mandatory."""
        return self.min_count != 0

    @property
    def is_list(self) -> bool:
        """Returns True if property contains a list of values."""
        return self.max_count != 1


class InformationRules(RuleModel):
    metadata: InformationMetadata = Field(alias="Metadata")
    properties: SheetList[InformationProperty] = Field(alias="Properties")
    classes: SheetList[InformationClass] = Field(alias="Classes")
    prefixes: dict[str, Namespace] = Field(default_factory=lambda: PREFIXES.copy())
    reference: "InformationRules | None" = Field(None, alias="Reference")

    @field_validator("prefixes", mode="before")
    def parse_str(cls, values: Any) -> Any:
        if isinstance(values, dict):
            return {key: Namespace(value) if isinstance(value, str) else value for key, value in values.items()}
        return values

    @model_validator(mode="after")
    def update_entities_prefix(self) -> Self:
        # update expected_value_types
        for property_ in self.properties:
            if isinstance(property_.value_type, ClassEntity) and property_.value_type.prefix is Undefined:
                property_.value_type.prefix = self.metadata.prefix
            if property_.class_.prefix is Undefined:
                property_.class_.prefix = self.metadata.prefix

        # update parent classes
        for class_ in self.classes:
            if class_.parent:
                for parent in cast(list[ParentClassEntity], class_.parent):
                    if not isinstance(parent.prefix, str):
                        parent.prefix = self.metadata.prefix
            if class_.class_.prefix is Undefined:
                class_.class_.prefix = self.metadata.prefix

        return self

    @model_validator(mode="after")
    def validate_schema_completeness(self) -> Self:
        # update expected_value_types

        if self.metadata.schema_ == SchemaCompleteness.complete:
            defined_classes = {str(class_.class_) for class_ in self.classes}
            referred_classes = {str(property_.class_) for property_ in self.properties} | {
                str(parent) for class_ in self.classes for parent in class_.parent or []
            }
            referred_types = {
                str(property_.value_type)
                for property_ in self.properties
                if isinstance(property_.value_type, Entity)
                and not isinstance(property_.value_type.suffix, _UnknownType)
            }
            if not referred_classes.issubset(defined_classes) or not referred_types.issubset(defined_classes):
                missing_classes = referred_classes.difference(defined_classes).union(
                    referred_types.difference(defined_classes)
                )
                raise exceptions.IncompleteSchema(missing_classes).to_pydantic_custom_error()

        return self

    @model_validator(mode="after")
    def validate_class_has_properties_or_parent(self) -> Self:
        defined_classes = {class_.class_ for class_ in self.classes if class_.reference is None}
        referred_classes = {property_.class_ for property_ in self.properties if property_.class_.suffix is not Unknown}
        has_parent_classes = {class_.class_ for class_ in self.classes if class_.parent}
        missing_classes = defined_classes.difference(referred_classes) - has_parent_classes
        if missing_classes:
            warnings.warn(
                cognite.neat.rules.issues.spreadsheet.ClassNoPropertiesNoParentsWarning(
                    [missing.versioned_id for missing in missing_classes]
                ),
                stacklevel=2,
            )
        return self

    @model_serializer(mode="plain", when_used="always")
    def information_rules_serializer(self, info: SerializationInfo) -> dict[str, Any]:
        kwargs = vars(info)
        default_prefix = f"{self.metadata.prefix}:" if self.metadata.prefix else ""

        field_names = ["Class", "Value Type"] if info.by_alias else ["class_", "value_type"]
        properties = []
        for prop in self.properties:
            dumped = prop.model_dump(**kwargs)
            for field_name in field_names:
                if value := dumped.get(field_name):
                    dumped[field_name] = value.removeprefix(default_prefix)
            properties.append(dumped)

        field_names = ["Class"] if info.by_alias else ["class_"]
        classes = []
        parent_name = "Parent Class" if info.by_alias else "parent"
        for cls in self.classes:
            dumped = cls.model_dump(**kwargs)
            for field_name in field_names:
                if value := dumped.get(field_name):
                    dumped[field_name] = value.removeprefix(default_prefix)
            if value := dumped.get(parent_name):
                dumped[parent_name] = ",".join(
                    constraint.strip().removeprefix(default_prefix) for constraint in value.split(",")
                )
            classes.append(dumped)

        return {
            "Metadata" if info.by_alias else "metadata": self.metadata.model_dump(**kwargs),
            "Classes" if info.by_alias else "classes": classes,
            "Properties" if info.by_alias else "properties": properties,
            "prefixes": {key: str(value) for key, value in self.prefixes.items()},
        }

    def as_domain_rules(self) -> DomainRules:
        return _InformationRulesConverter(self).as_domain_rules()

    def as_dms_architect_rules(self) -> "DMSRules":
        return _InformationRulesConverter(self).as_dms_architect_rules()

    def reference_self(self) -> "InformationRules":
        new_self = self.model_copy(deep=True)
        for prop in new_self.properties:
            prop.reference = ReferenceEntity(
                prefix=prop.class_.prefix
                if not isinstance(prop.class_.prefix, _UndefinedType)
                else self.metadata.prefix,
                suffix=prop.class_.suffix,
                version=prop.class_.version,
                property=prop.property_,
            )

        for cls_ in new_self.classes:
            cls_.reference = ReferenceEntity(
                prefix=cls_.class_.prefix
                if not isinstance(cls_.class_.prefix, _UndefinedType)
                else self.metadata.prefix,
                suffix=cls_.class_.suffix,
                version=cls_.class_.version,
            )

        return new_self


class _InformationRulesConverter:
    def __init__(self, information: InformationRules):
        self.information = information

    def as_domain_rules(self) -> DomainRules:
        raise NotImplementedError("DomainRules not implemented yet")

    def as_dms_architect_rules(self, created: datetime | None = None, updated: datetime | None = None) -> "DMSRules":
        from ._dms_architect_rules import DMSContainer, DMSMetadata, DMSProperty, DMSRules, DMSView

        info_metadata = self.information.metadata
        default_version = info_metadata.version
        default_space = self._to_space(info_metadata.prefix)
        space = self._to_space(info_metadata.prefix)

        metadata = DMSMetadata(
            schema_=info_metadata.schema_,
            space=space,
            version=info_metadata.version,
            external_id=info_metadata.name.replace(" ", "_").lower(),
            creator=info_metadata.creator,
            name=info_metadata.name,
            created=created or datetime.now(),
            updated=updated or datetime.now(),
        )

        properties_by_class: dict[str, list[DMSProperty]] = defaultdict(list)
        for prop in self.information.properties:
            properties_by_class[prop.class_.versioned_id].append(
                self._as_dms_property(prop, default_space, default_version)
            )

        views: list[DMSView] = [
            DMSView(
                class_=cls_.class_,
                name=cls_.name,
                view=cls_.class_.as_view_entity(default_space, default_version),
                description=cls_.description,
                reference=cls_.reference,
                implements=self._get_view_implements(cls_, info_metadata),
            )
            for cls_ in self.information.classes
        ]

        classes_without_properties: set[str] = set()
        for class_ in self.information.classes:
            properties: list[DMSProperty] = properties_by_class.get(class_.class_.versioned_id, [])
            if not properties or all(
                isinstance(prop.value_type, ViewPropertyEntity) and prop.relation != "direct" for prop in properties
            ):
                classes_without_properties.add(class_.class_.versioned_id)

        containers: list[DMSContainer] = []
        for class_ in self.information.classes:
            if class_.class_.versioned_id in classes_without_properties:
                continue
            containers.append(
                DMSContainer(
                    class_=class_.class_,
                    name=class_.name,
                    container=class_.class_.as_container_entity(default_space),
                    description=class_.description,
                    constraint=[
                        parent.as_container_entity(default_space)
                        for parent in class_.parent or []
                        if parent.versioned_id not in classes_without_properties
                    ]
                    or None,
                )
            )

        return DMSRules(
            metadata=metadata,
            properties=SheetList[DMSProperty](
                data=[prop for prop_set in properties_by_class.values() for prop in prop_set]
            ),
            views=SheetList[DMSView](data=views),
            containers=SheetList[DMSContainer](data=containers),
            reference=self.information.reference and self.information.reference.as_dms_architect_rules(),  # type: ignore[arg-type]
        )

    @classmethod
    def _as_dms_property(cls, prop: InformationProperty, default_space: str, default_version: str) -> "DMSProperty":
        """This creates the first"""

        from ._dms_architect_rules import DMSProperty

        # returns property type, which can be ObjectProperty or DatatypeProperty
        value_type: DataType | ViewEntity | ViewPropertyEntity | DMSUnknownEntity
        if isinstance(prop.value_type, DataType):
            value_type = prop.value_type
        elif isinstance(prop.value_type, UnknownEntity):
            value_type = DMSUnknownEntity()
        elif isinstance(prop.value_type, ClassEntity):
            value_type = prop.value_type.as_view_entity(default_space, default_version)
        else:
            raise ValueError(f"Unsupported value type: {prop.value_type.type_}")

        relation: Literal["direct", "multiedge"] | None = None
        if isinstance(value_type, ViewEntity | ViewPropertyEntity):
            relation = "multiedge" if prop.is_list else "direct"

        container: ContainerEntity | None = None
        container_property: str | None = None
        is_list: bool | None = prop.is_list
        nullable: bool | None = not prop.is_mandatory
        if relation == "multiedge":
            is_list = None
            nullable = None
        elif relation == "direct":
            nullable = True
            container, container_property = cls._get_container(prop, default_space)
        else:
            container, container_property = cls._get_container(prop, default_space)

        return DMSProperty(
            class_=prop.class_,
            name=prop.name,
            property_=prop.property_,
            value_type=value_type,
            nullable=nullable,
            is_list=is_list,
            relation=relation,
            default=prop.default,
            reference=prop.reference,
            container=container,
            container_property=container_property,
            view=prop.class_.as_view_entity(default_space, default_version),
            view_property=prop.property_,
        )

    @classmethod
    def _to_space(cls, prefix: str) -> str:
        """Ensures that the prefix comply with the CDF space regex"""
        prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", prefix)
        if prefix[0].isdigit() or prefix[0] == "_":
            prefix = f"a{prefix}"
        prefix = prefix[:43]
        if prefix[-1] == "_":
            prefix = f"{prefix[:-1]}1"
        return prefix

    @classmethod
    def _get_container(cls, prop: InformationProperty, default_space: str) -> tuple[ContainerEntity, str]:
        if isinstance(prop.reference, ReferenceEntity):
            return (
                prop.reference.as_container_entity(default_space),
                prop.reference.property_ or prop.property_,
            )
        else:
            return prop.class_.as_container_entity(default_space), prop.property_

    @classmethod
    def _get_view_implements(cls, cls_: InformationClass, metadata: InformationMetadata) -> list[ViewEntity]:
        if isinstance(cls_.reference, ReferenceEntity) and cls_.reference.prefix != metadata.prefix:
            # We use the reference for implements if it is in a different namespace
            implements = [
                cls_.reference.as_view_entity(metadata.prefix, metadata.version),
            ]
        else:
            implements = []

        implements.extend([parent.as_view_entity(metadata.prefix, metadata.version) for parent in cls_.parent or []])
        return implements
