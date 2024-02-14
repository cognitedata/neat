import re
import sys
import warnings
from datetime import datetime
from typing import Any, ClassVar

from pydantic import Field, HttpUrl, TypeAdapter, field_validator, model_validator
from rdflib import Namespace, URIRef

from cognite.neat.rules import exceptions
from cognite.neat.rules.models._base import EntityTypes
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

from .base import (
    Prefix,
    RoleTypes,
    RuleModel,
    SheetList,
    prefix_compliance_regex,
    version_compliance_regex,
)
from .domain_rules import DomainClass, DomainMetadata, DomainProperty

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum


class MatchType(StrEnum):
    exact = "exact"
    partial = "partial"


class InformationMetadata(DomainMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.information_architect
    prefix: Prefix = Field(
        description="This is used as prefix for generation of RDF OWL/SHACL data model representation",
    )
    namespace: Namespace = Field(
        description="This is used as RDF namespace for generation of RDF OWL/SHACL data model representation "
        "and/or for generation of RDF graphs.",
        min_length=1,
        max_length=2048,
    )

    name: str = Field(
        alias="title",
        description="Human readable name of the data model",
        min_length=1,
        max_length=255,
    )

    version: str | None = Field(
        description="Data model version",
        min_length=1,
        max_length=43,
    )

    contributor: str | list[str] = Field(
        description=(
            "List of contributors to the data model creation, "
            "typically information architects are considered as contributors."
        ),
    )

    created: datetime = Field(
        description=("Date of the data model creation"),
    )

    updated: datetime = Field(
        description=("Date of the data model update"),
    )

    @field_validator("version")
    def is_version_compliant(cls, value):
        if not re.match(version_compliance_regex, value):
            raise exceptions.VersionRegexViolation(value, version_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @field_validator("prefix")
    def is_prefix_compliant(cls, value):
        if not re.match(prefix_compliance_regex, value):
            raise exceptions.PrefixesRegexViolation([value], prefix_compliance_regex).to_pydantic_custom_error()
        return value

    @field_validator("contributor", mode="before")
    def contributor_to_list_if_comma(cls, value):
        if isinstance(value, str):
            if value:
                return value.replace(", ", ",").split(",")
        return value

    @field_validator("namespace", mode="before")
    def fix_namespace_ending(cls, value):
        if value.endswith("#") or value.endswith("/"):
            return Namespace(TypeAdapter(HttpUrl).validate_python(value))
        warnings.warn(
            exceptions.NamespaceEndingFixed(value).message, category=exceptions.NamespaceEndingFixed, stacklevel=2
        )
        return Namespace(TypeAdapter(HttpUrl).validate_python(f"{value}#"))

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


class InformationClass(DomainClass):
    """
    Class is a category of things that share a common set of attributes and relationships.

    Args:
        class_: The class ID of the class.
        description: A description of the class.
        parent: The parent class of the class.
        source: Source of information for given resource
        match_type: The match type of the resource being described and the source entity.
    """

    source: Namespace | None = None
    match_type: MatchType | None = None

    @field_validator("source", mode="before")
    def fix_namespace_ending(cls, value):
        if value:
            return Namespace(TypeAdapter(HttpUrl).validate_python(value))
        return value


class InformationProperty(DomainProperty):
    """
    A property is a characteristic of a class. It is a named attribute of a class that describes a range of values
    or a relationship to another class.

    Args:
        class_: Class ID to which property belongs
        property: Property ID of the property
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

    default: Any | None = Field(alias="Default", default=None)
    source: URIRef | None = None
    match_type: MatchType | None = None
    rule_type: str | TransformationRuleType | None = Field(alias="Rule Type", default=None)
    rule: str | AllReferences | SingleProperty | Hop | RawLookup | SPARQLQuery | Traversal | None = Field(
        alias="Rule", default=None
    )

    @field_validator("source", mode="before")
    def fix_namespace_ending(cls, value):
        if value:
            return URIRef(TypeAdapter(HttpUrl).validate_python(value))
        return value

    @model_validator(mode="after")
    def is_valid_rule(self):
        if self.rule_type:
            self.rule_type = self.rule_type.lower()
            if not self.rule:
                raise exceptions.RuleTypeProvidedButRuleMissing(
                    self.property, self.class_, self.rule_type
                ).to_pydantic_custom_error()
            self.rule = parse_rule(self.rule, self.rule_type)
        return self

    @model_validator(mode="after")
    def set_default_as_list(self):
        if (
            self.type_ == EntityTypes.data_property
            and self.default
            and self.isList
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
                        self.property_id,
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
    def isMandatory(self) -> bool:
        """Returns True if property is mandatory."""
        return self.min_count != 0

    @property
    def isList(self) -> bool:
        """Returns True if property contains a list of values."""
        return self.max_count != 1


class InformationRules(RuleModel):
    metadata: InformationMetadata = Field(alias="Metadata")
    properties: SheetList[InformationProperty] = Field(alias="Properties")
    classes: SheetList[InformationClass] = Field(alias="Classes")
