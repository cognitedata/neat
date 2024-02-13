import re
import warnings
from datetime import datetime
import sys
from typing import Any, ClassVar

from pydantic import Field, HttpUrl, TypeAdapter, field_validator
from rdflib import Namespace

from cognite.neat.rules import exceptions
from cognite.neat.rules.models.rdfpath import (
    AllReferences,
    Hop,
    RawLookup,
    SingleProperty,
    SPARQLQuery,
    TransformationRuleType,
    Traversal,
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
        source: Source of information for given resource
        match_type: The match type of the resource being described and the source entity.
        rule_type: Rule type for the transformation from source to target representation
                   of knowledge graph. Defaults to None (no transformation)
        rule: Actual rule for the transformation from source to target representation of
              knowledge graph. Defaults to None (no transformation)
    """

    default: Any | None = Field(alias="Default", default=None)
    source: Namespace | None = None
    match_type: MatchType | None = None
    rule_type: TransformationRuleType | None = Field(alias="Rule Type", default=None)
    rule: str | AllReferences | SingleProperty | Hop | RawLookup | SPARQLQuery | Traversal | None = Field(
        alias="Rule", default=None
    )

    @field_validator("source", mode="before")
    def fix_namespace_ending(cls, value):
        if value:
            return Namespace(TypeAdapter(HttpUrl).validate_python(value))
        return value


class InformationRules(RuleModel):
    metadata: InformationMetadata = Field(alias="Metadata")
    properties: SheetList[InformationProperty] = Field(alias="Properties")
    classes: SheetList[InformationClass] = Field(alias="Classes")
