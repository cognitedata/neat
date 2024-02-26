import sys
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, cast

from pydantic import Field, model_validator
from rdflib import Namespace

from cognite.neat.rules import exceptions
from cognite.neat.rules.models._base import EntityTypes, ParentClass
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
    ClassType,
    ContainerEntity,
    NamespaceType,
    ParentClassType,
    PrefixType,
    PropertyType,
    SourceType,
    StrListType,
    ValueTypeType,
    VersionType,
    ViewEntity,
)
from .base import BaseMetadata, MatchType, RoleTypes, RuleModel, SheetEntity, SheetList
from .domain_rules import DomainMetadata, DomainRules

if TYPE_CHECKING:
    from .dms_architect_rules import DMSProperty, DMSRules


if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class InformationMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.information_architect
    prefix: PrefixType
    namespace: NamespaceType

    name: str = Field(
        alias="title",
        description="Human readable name of the data model",
        min_length=1,
        max_length=255,
    )

    version: VersionType

    created: datetime = Field(
        description=("Date of the data model creation"),
    )

    updated: datetime = Field(
        description=("Date of the data model update"),
    )
    contributor: StrListType = Field(
        description=(
            "List of contributors to the data model creation, "
            "typically information architects are considered as contributors."
        ),
    )

    @classmethod
    def from_domain_expert_metadata(
        cls,
        metadata: DomainMetadata,
        prefix: str | None = None,
        namespace: Namespace | None = None,
        version: str | None = None,
        contributor: str | list[str] | None = None,
        created: datetime | None = None,
        updated: datetime | None = None,
    ):
        metadata_as_dict = metadata.model_dump()
        metadata_as_dict["prefix"] = prefix or "neat"
        metadata_as_dict["namespace"] = namespace or Namespace("http://purl.org/cognite/neat#")
        metadata_as_dict["version"] = version or "0.1.0"
        metadata_as_dict["contributor"] = contributor or "Cognite"
        metadata_as_dict["created"] = created or datetime.utcnow()
        metadata_as_dict["updated"] = updated or datetime.utcnow()
        return cls(**metadata_as_dict)


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

    class_: ClassType = Field(alias="Class")
    description: str | None = Field(alias="Description", default=None)
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

    # TODO: Can we skip rule_type and simply try to parse the rule and if it fails, raise an error?
    class_: ClassType = Field(alias="Class")
    property_: PropertyType = Field(alias="Property")
    value_type: ValueTypeType = Field(alias="Value Type")
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
        if self.value_type.type_ == EntityTypes.data_value_type:
            return EntityTypes.data_property
        elif self.value_type.type_ == EntityTypes.object_value_type:
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

    @model_validator(mode="after")
    def update_entities_prefix(self) -> Self:
        # update expected_value_types
        for property_ in self.properties:
            if property_.value_type.prefix == "undefined":
                property_.value_type.prefix = self.metadata.prefix

        # update parent classes
        for class_ in self.classes:
            if class_.parent:
                for parent in cast(list[ParentClass], class_.parent):
                    if parent.prefix == "undefined":
                        parent.prefix = self.metadata.prefix

        return self

    def as_domain_rules(self) -> DomainRules:
        return _InformationRulesConverter(self).as_domain_rules()

    def as_dms_architect_rules(self) -> DMSRules:
        return _InformationRulesConverter(self).as_dms_architect_rules()


class _InformationRulesConverter:
    def __init__(self, information: InformationRules):
        self.information = information

    def as_domain_rules(self) -> DomainRules:
        raise NotImplementedError("DomainRules not implemented yet")

    def as_dms_architect_rules(self) -> DMSRules:
        from .dms_architect_rules import DMSContainer, DMSMetadata, DMSProperty, DMSRules, DMSView

        info_metadata = self.information.metadata

        metadata = DMSMetadata(
            schema_="partial",
            space=info_metadata.prefix,
            version=info_metadata.version,
            external_id=info_metadata.name.replace(" ", "_").lower(),
            contributor=info_metadata.contributor,
        )

        properties_by_class: dict[str, list[DMSProperty]] = defaultdict(list)
        for prop in self.information.properties:
            properties_by_class[prop.class_].append(self._as_dms_property(prop))

        views: list[DMSView] = [
            DMSView(
                class_=cls_.class_,
                view=ViewEntity(prefix=info_metadata.prefix, suffix=cls_.class_),
                description=cls_.description,
                implements=[
                    ViewEntity(prefix=parent.prefix, suffix=parent.suffix, version=parent.version)
                    for parent in cls_.parent or []
                ],
            )
            for cls_ in self.information.classes
        ]

        containers: list[DMSContainer] = []
        classes_without_properties: set[str] = set()
        for class_ in self.information.classes:
            properties: list[DMSProperty] = properties_by_class.get(class_.class_, [])
            if not properties or all(
                isinstance(prop.value_type, ViewEntity) and not prop.value_type != "direct" for prop in properties
            ):
                classes_without_properties.add(class_.class_)
                continue

            containers.append(
                DMSContainer(
                    class_=class_.class_,
                    container=ContainerEntity(prefix=info_metadata.prefix, suffix=class_.class_),
                    description=class_.description,
                    constraint=[
                        ContainerEntity(prefix=info_metadata.prefix, suffix=class_.class_)
                        for parent in class_.parent or []
                        if parent.id not in classes_without_properties
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

    @staticmethod
    def _as_dms_property(prop: InformationProperty) -> DMSProperty:
        """This creates the first"""

        from .dms_architect_rules import DMSProperty

        if dms_type := prop.value_type.dms:
            value_type = dms_type._type.casefold()  # type: ignore[attr-defined]
        else:
            value_type = ViewEntity(
                prefix=prop.value_type.prefix, suffix=prop.value_type.suffix, version=prop.value_type.version
            )

        return DMSProperty(
            class_=prop.class_,
            property_=prop.property_,
            value_type=value_type,
            nullable=not prop.is_mandatory,
            is_list=prop.is_list,
            default=prop.default,
            source=prop.source,
            container=ContainerEntity.from_raw(prop.class_),
            container_property=prop.property_,
            view=ViewEntity.from_raw(prop.class_),
            view_property=prop.property_,
        )
