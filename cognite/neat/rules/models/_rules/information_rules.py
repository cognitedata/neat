from datetime import datetime
import re
import warnings
from pydantic import Field, TypeAdapter, field_validator, HttpUrl

from rdflib import Namespace

from cognite.neat.rules import exceptions
from .base import Prefix, RoleTypes, RuleModel, skip_field_validator
from .base import version_compliance_regex, prefix_compliance_regex, more_than_one_none_alphanumerics_regex
from .domain_rules import DomainMetadata


class InformationArchitectMetadata(DomainMetadata):

    role: RoleTypes = RoleTypes.information_architect
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
        else:
            return value

    @field_validator("creator", "contributor", mode="before")
    def to_list_if_comma(cls, value, values):
        if isinstance(value, str):
            if value:
                return value.replace(", ", ",").split(",")
            if cls.model_fields[values.field_name].default is None:
                return None
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
        name: str | None = None,
    ):
        metadata_as_dict = metadata.model_dump()
        metadata_as_dict["prefix"] = prefix or metadata.prefix or "neat"
        metadata_as_dict["namespace"] = namespace or metadata.namespace or Namespace("http://purl.org/cognite/neat#")
        metadata_as_dict["version"] = version or metadata.version or "0.1.0"
        metadata_as_dict["contributor"] = contributor or metadata.contributor or "Cognite"
        metadata_as_dict["created"] = created or metadata.created or datetime.utcnow()
        metadata_as_dict["updated"] = updated or metadata.updated or datetime.utcnow()
        metadata_as_dict["name"] = name or metadata.name or "NEAT Data Model"
        return cls(**metadata_as_dict)


class InformationArchitectRules(RuleModel):
    metadata: InformationArchitectMetadata
