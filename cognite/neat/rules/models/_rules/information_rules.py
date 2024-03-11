import re
import sys
import warnings
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from pydantic import Field, model_validator
from rdflib import Namespace

from cognite.neat.constants import PREFIXES
from cognite.neat.rules import exceptions, validation
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

from ._types import (
    ClassEntity,
    ContainerEntity,
    EntityTypes,
    NamespaceType,
    ParentClassEntity,
    ParentClassType,
    PrefixType,
    PropertyType,
    SemanticValueType,
    SourceType,
    StrListType,
    Undefined,
    VersionType,
    ViewEntity,
    XSDValueType,
)
from .base import BaseMetadata, MatchType, RoleTypes, RuleModel, SchemaCompleteness, SheetEntity, SheetList
from .domain_rules import DomainRules

if TYPE_CHECKING:
    from .dms_architect_rules import DMSProperty, DMSRules


if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class InformationMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.information_architect
    schema_: SchemaCompleteness = Field(alias="schema")
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


class InformationClass(SheetEntity):
    """
    Class is a category of things that share a common set of attributes and relationships.

    Args:
        class_: The class ID of the class.
        description: A description of the class.
        parent: The parent class of the class.
        source: Source of information for given resource
        match_type: The match type of the resource being described and the source entity.
    """

    parent: ParentClassType = Field(alias="Parent Class", default=None)
    source: SourceType = Field(alias="Source", default=None)
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
        source: Source of information for given resource, HTTP URI
        match_type: The match type of the resource being described and the source entity.
        rule_type: Rule type for the transformation from source to target representation
                   of knowledge graph. Defaults to None (no transformation)
        rule: Actual rule for the transformation from source to target representation of
              knowledge graph. Defaults to None (no transformation)
    """

    property_: PropertyType = Field(alias="Property")
    value_type: SemanticValueType = Field(alias="Value Type")
    min_count: int | None = Field(alias="Min Count", default=None)
    max_count: int | float | None = Field(alias="Max Count", default=None)
    default: Any | None = Field(alias="Default", default=None)
    source: SourceType = Field(alias="Source", default=None)
    match_type: MatchType | None = Field(alias="Match Type", default=None)
    rule_type: str | TransformationRuleType | None = Field(alias="Rule Type", default=None)
    rule: str | AllReferences | SingleProperty | Hop | RawLookup | SPARQLQuery | Traversal | None = Field(
        alias="Rule", default=None
    )
    comment: str | None = Field(alias="Comment", default=None)

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
        if self.value_type.type_ == EntityTypes.xsd_value_type:
            return EntityTypes.data_property
        elif self.value_type.type_ == EntityTypes.class_:
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

    @model_validator(mode="after")
    def update_entities_prefix(self) -> Self:
        # update expected_value_types
        for property_ in self.properties:
            if property_.value_type.prefix is Undefined:
                property_.value_type.prefix = self.metadata.prefix
            if property_.class_.prefix is Undefined:
                property_.class_.prefix = self.metadata.prefix

        # update parent classes
        for class_ in self.classes:
            if class_.parent:
                for parent in cast(list[ParentClassEntity], class_.parent):
                    if parent.prefix is Undefined:
                        parent.prefix = self.metadata.prefix
            if class_.class_.prefix is Undefined:
                class_.class_.prefix = self.metadata.prefix

        return self

    @model_validator(mode="after")
    def validate_schema_completeness(self) -> Self:
        # update expected_value_types

        if self.metadata.schema_ == SchemaCompleteness.complete:
            defined_classes = {class_.class_.versioned_id for class_ in self.classes}
            referred_classes = {property_.class_.versioned_id for property_ in self.properties} | {
                parent.versioned_id for class_ in self.classes for parent in class_.parent or []
            }
            referred_types = {
                property_.value_type.versioned_id
                for property_ in self.properties
                if property_.type_ == EntityTypes.object_property
            }
            if not referred_classes.issubset(defined_classes) or not referred_types.issubset(defined_classes):
                missing_classes = referred_classes.difference(defined_classes).union(
                    referred_types.difference(defined_classes)
                )
                raise exceptions.IncompleteSchema(missing_classes).to_pydantic_custom_error()

        return self

    @model_validator(mode="after")
    def validate_class_has_properties_or_parent(self) -> Self:
        defined_classes = {class_.class_ for class_ in self.classes}
        referred_classes = {property_.class_ for property_ in self.properties}
        has_parent_classes = {class_.class_ for class_ in self.classes if class_.parent}
        missing_classes = defined_classes.difference(referred_classes) - has_parent_classes
        if missing_classes:
            warnings.warn(
                validation.ClassNoPropertiesNoParents([missing.versioned_id for missing in missing_classes]),
                stacklevel=2,
            )
        return self

    def as_domain_rules(self) -> DomainRules:
        return _InformationRulesConverter(self).as_domain_rules()

    def as_dms_architect_rules(self) -> "DMSRules":
        return _InformationRulesConverter(self).as_dms_architect_rules()


class _InformationRulesConverter:
    def __init__(self, information: InformationRules):
        self.information = information

    def as_domain_rules(self) -> DomainRules:
        raise NotImplementedError("DomainRules not implemented yet")

    def as_dms_architect_rules(self, created: datetime | None = None, updated: datetime | None = None) -> "DMSRules":
        from .dms_architect_rules import DMSContainer, DMSMetadata, DMSProperty, DMSRules, DMSView

        info_metadata = self.information.metadata

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
            properties_by_class[prop.class_.versioned_id].append(self._as_dms_property(prop))

        views: list[DMSView] = [
            DMSView(
                class_=cls_.class_,
                view=ViewEntity(prefix=cls_.class_.prefix, suffix=cls_.class_.suffix, version=cls_.class_.version),
                description=cls_.description,
                implements=[
                    ViewEntity(prefix=parent.prefix, suffix=parent.suffix, version=parent.version)
                    for parent in cls_.parent or []
                ],
            )
            for cls_ in self.information.classes
        ]

        classes_without_properties: set[str] = set()
        for class_ in self.information.classes:
            properties: list[DMSProperty] = properties_by_class.get(class_.class_.versioned_id, [])
            if not properties or all(
                isinstance(prop.value_type, ViewEntity) and prop.relation != "direct" for prop in properties
            ):
                classes_without_properties.add(class_.class_.versioned_id)

        containers: list[DMSContainer] = []
        for class_ in self.information.classes:
            if class_.class_.versioned_id in classes_without_properties:
                continue
            containers.append(
                DMSContainer(
                    class_=class_.class_,
                    container=ContainerEntity(prefix=class_.class_.prefix, suffix=class_.class_.suffix),
                    description=class_.description,
                    constraint=[
                        ContainerEntity(
                            prefix=parent.prefix,
                            suffix=parent.suffix,
                        )
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
        )

    @classmethod
    def _as_dms_property(cls, prop: InformationProperty) -> "DMSProperty":
        """This creates the first"""

        from .dms_architect_rules import DMSProperty

        # returns property type, which can be ObjectProperty or DatatypeProperty
        if isinstance(prop.value_type, XSDValueType):
            value_type = cast(XSDValueType, prop.value_type).dms._type.casefold()  # type: ignore[attr-defined]
        elif isinstance(prop.value_type, ClassEntity):
            value_type = ViewEntity(
                prefix=prop.value_type.prefix, suffix=prop.value_type.suffix, version=prop.value_type.version
            )
        else:
            raise ValueError(f"Unsupported value type: {prop.value_type.type_}")

        relation: Literal["direct", "multiedge"] | None = None
        if isinstance(value_type, ViewEntity):
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
            container = ContainerEntity(prefix=prop.class_.prefix, suffix=prop.class_.suffix)
            container_property = prop.property_
        else:
            container = ContainerEntity(prefix=prop.class_.prefix, suffix=prop.class_.suffix)
            container_property = prop.property_

        try:
            return DMSProperty(
                class_=prop.class_,
                property_=prop.property_,
                value_type=value_type,
                nullable=nullable,
                is_list=is_list,
                relation=relation,
                default=prop.default,
                source=prop.source,
                container=container,
                container_property=container_property,
                view=ViewEntity(prefix=prop.class_.prefix, suffix=prop.class_.suffix, version=prop.class_.version),
                view_property=prop.property_,
            )
        except ValueError:
            raise

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
