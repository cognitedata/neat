"""This module contains the definition of `TransformationRules` pydantic model and all
its sub-models and validators.
"""

from __future__ import annotations

import inspect
import math
import re
import sys
import warnings
from collections.abc import ItemsView, Iterator, KeysView, ValuesView
from datetime import datetime
from pathlib import Path
from types import FrameType
from typing import Any, ClassVar, Generic, TypeAlias, TypeVar, cast

import pandas as pd
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    ValidationError,
    constr,
    field_validator,
    model_validator,
    parse_obj_as,
    validator,
)
from pydantic.fields import FieldInfo
from rdflib import XSD, Literal, Namespace, URIRef

from cognite.neat.constants import PREFIXES
from cognite.neat.rules import exceptions
from cognite.neat.rules.models.rdfpath import (
    AllReferences,
    Entity,
    Hop,
    RawLookup,
    SingleProperty,
    SPARQLQuery,
    TransformationRuleType,
    Traversal,
    parse_rule,
)
from cognite.neat.rules.type_mapping import DATA_TYPE_MAPPING, type_to_target_convention

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

__all__ = [
    "Class",
    "Classes",
    "Instance",
    "Metadata",
    "Prefixes",
    "Property",
    "Properties",
    "Resource",
    "Rules",
]

METADATA_VALUE_MAX_LENGTH = 5120


def replace_nan_floats_with_default(values: dict, model_fields: dict[str, FieldInfo]) -> dict:
    output = {}
    for field_name, value in values.items():
        is_nan_float = isinstance(value, float) and math.isnan(value)
        if not is_nan_float:
            output[field_name] = value
            continue
        if field_name in model_fields:
            output[field_name] = model_fields[field_name].default
        else:
            # field_name may be an alias
            source_name = next((name for name, field in model_fields.items() if field.alias == field_name), None)
            if source_name:
                output[field_name] = model_fields[source_name].default
            else:
                # Just pass it through if it is not an alias.
                output[field_name] = value
    return output


class RuleModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, arbitrary_types_allowed=True, strict=False, extra="allow"
    )

    @classmethod
    def mandatory_fields(cls, use_alias=False) -> set[str]:
        """Returns a set of mandatory fields for the model."""
        return _get_required_fields(cls, use_alias)


def _get_required_fields(model: type[BaseModel], use_alias: bool = False) -> set[str]:
    """Get required fields from a pydantic model.

    Parameters
    ----------
    model : type[BaseModel]
        Pydantic data model
    use_alias : bool, optional
        Whether to return field alias name, by default False

    Returns
    -------
    list[str]
        List of required fields
    """
    required_fields = set()
    for name, field in model.model_fields.items():
        if not field.is_required():
            continue

        alias = getattr(field, "alias", None)
        if use_alias and alias:
            required_fields.add(alias)
        else:
            required_fields.add(name)
    return required_fields


class URL(BaseModel):
    url: HttpUrl


Description: TypeAlias = constr(min_length=1, max_length=255)  # type: ignore[valid-type]

# regex expressions for compliance of Metadata sheet parsing
more_than_one_none_alphanumerics_regex = r"([_-]{2,})"
prefix_compliance_regex = r"^([a-zA-Z]+)([a-zA-Z0-9]*[_-]{0,1}[a-zA-Z0-9_-]*)([a-zA-Z0-9]*)$"
data_model_id_compliance_regex = r"^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$"
cdf_space_name_compliance_regex = (
    r"(?!^(space|cdf|dms|pg3|shared|system|node|edge)$)(^[a-zA-Z][a-zA-Z0-9_]{0,41}[a-zA-Z0-9]?$)"
)
view_id_compliance_regex = (
    r"(?!^(Query|Mutation|Subscription|String|Int32|Int64|Int|Float32|Float64|Float|"
    r"Timestamp|JSONObject|Date|Numeric|Boolean|PageInfo|File|Sequence|TimeSeries)$)"
    r"(^[a-zA-Z][a-zA-Z0-9_]{0,253}[a-zA-Z0-9]?$)"
)
dms_property_id_compliance_regex = (
    r"(?!^(space|externalId|createdTime|lastUpdatedTime|deletedTime|edge_id|"
    r"node_id|project_id|property_group|seq|tg_table_name|extensions)$)"
    r"(^[a-zA-Z][a-zA-Z0-9_]{0,253}[a-zA-Z0-9]?$)"
)


class_id_compliance_regex = r"(?!^(Class|class)$)(^[a-zA-Z][a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]?$)"
property_id_compliance_regex = r"^(\*)|(?!^(Property|property)$)(^[a-zA-Z][a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]?$)"

version_compliance_regex = (
    r"^([0-9]+[_-]{1}[0-9]+[_-]{1}[0-9]+[_-]{1}[a-zA-Z0-9]+)|"
    r"([0-9]+[_-]{1}[0-9]+[_-]{1}[0-9]+)|([0-9]+[_-]{1}[0-9])|([0-9]+)$"
)

Prefix: TypeAlias = str
ExternalId: TypeAlias = str


class Metadata(RuleModel):
    """
    Metadata model for data model

    Args:
        prefix: This is used as prefix for generation of RDF OWL/SHACL data model representation
        cdf_space_name: This is used as CDF space name to which model is intend to be stored. By default it is set to
                        'playground'
        namespace: This is used as RDF namespace for generation of RDF OWL/SHACL data model representation and/or for
                   generation of RDF graphs
        data_model_name: This is used as RDF data model name for generation of RDF OWL/SHACL data model representation
                         and/or for generation of RDF graphs
        version: This is used as RDF data model version for generation of RDF OWL/SHACL data model representation
                 and/or for generation of RDF graphs
        is_current_version: This is used as RDF data model version for generation of RDF OWL/SHACL data model
        created: This is used as RDF data model creation date for generation of RDF OWL/SHACL data model representation
        updated: This is used as RDF data model update date for generation of RDF OWL/SHACL data model representation
        title: This is used as RDF data model title for generation of RDF OWL/SHACL data model representation
        description: This is used as RDF data model description for generation of RDF
                     OWL/SHACL data model representation
        creator: This is used as RDF data model creator for generation of RDF OWL/SHACL data model representation
        contributor: This is used as RDF data model contributor for generation of
                     RDF OWL/SHACL data model representation
        rights: This is used as RDF data model rights for generation of RDF OWL/SHACL data model representation
        externalIdPrefix: This is used as RDF data model externalIdPrefix for generation of RDF OWL/SHACL data model
        data_set_id: This is used as RDF data model data_set_id for generation of
                     RDF OWL/SHACL data model representation
        source: This is used as RDF data model source for generation of RDF OWL/SHACL data model representation
        dms_compliant: This is used as RDF data model dms_compliant for generation of RDF OWL/SHACL data model

    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, arbitrary_types_allowed=True
    )
    prefix: Prefix = Field(
        alias="shortName",
        description="This is used as prefix for generation of RDF OWL/SHACL data model representation",
    )
    cdf_space_name: Prefix = Field(
        description="This is used as CDF space name to which model is intend to be stored. "
        "By default it is set to 'playground'",
        alias="cdfSpaceName",
        default="playground",
    )

    namespace: Namespace | None = Field(
        description="This is used as RDF namespace for generation of RDF OWL/SHACL data model representation "
        "and/or for generation of RDF graphs",
        min_length=1,
        max_length=2048,
        default=None,
    )
    data_model_name: ExternalId | None = Field(
        description="Name that uniquely identifies data model",
        alias="dataModelName",
        default=None,
        min_length=1,
        max_length=255,
    )

    version: str = Field(min_length=1, max_length=43)
    is_current_version: bool = Field(alias="isCurrentVersion", default=True)
    created: datetime
    updated: datetime = Field(default_factory=lambda: datetime.utcnow())
    title: str = Field(min_length=1, max_length=255)
    description: Description
    creator: str | list[str]
    contributor: str | list[str] | None = None
    rights: str | None = "Restricted for Internal Use of Cognite"
    externalIdPrefix: str = Field(alias="externalIdPrefix", default="")
    data_set_id: int | None = Field(alias="dataSetId", default=None)
    source: str | Path | None = Field(
        description="File path to Excel file which was used to produce Transformation Rules", default=None
    )
    dms_compliant: bool = True

    @field_validator("externalIdPrefix", "contributor", "contributor", "description", "rights", mode="before")
    def replace_float_nan_with_default(cls, value, info):
        if isinstance(value, float) and math.isnan(value):
            return cls.model_fields[info.field_name].default
        return value

    @field_validator("version", mode="before")
    def convert_to_string(cls, value):
        return str(value)

    @validator("prefix", always=True)
    def is_prefix_compliant(cls, value):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("prefix", value).to_pydantic_custom_error()
        if not re.match(prefix_compliance_regex, value):
            raise exceptions.PrefixRegexViolation(value, prefix_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("cdf_space_name", always=True)
    def is_cdf_space_name_compliant(cls, value):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("cdf_space_name", value).to_pydantic_custom_error()
        if not re.match(cdf_space_name_compliance_regex, value):
            raise exceptions.CDFSpaceRegexViolation(value, cdf_space_name_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("namespace", always=True)
    def set_namespace_if_none(cls, value, values):
        if value is None:
            if values["cdf_space_name"] == "playground":
                return Namespace(f"http://purl.org/cognite/{values['prefix']}#")
            else:
                return Namespace(f"http://purl.org/cognite/{values['cdf_space_name']}/{values['prefix']}#")
        try:
            return Namespace(parse_obj_as(HttpUrl, value))
        except ValidationError as e:
            raise exceptions.MetadataSheetNamespaceNotValidURL(value).to_pydantic_custom_error() from e

    @validator("namespace", always=True)
    def fix_namespace_ending(cls, value):
        if value.endswith("#") or value.endswith("/"):
            return value
        warnings.warn(
            exceptions.NamespaceEndingFixed(value).message, category=exceptions.NamespaceEndingFixed, stacklevel=2
        )
        return Namespace(f"{value}#")

    @validator("data_model_name", always=True)
    def set_data_model_name_if_none(cls, value, values):
        if value is not None:
            return value
        warnings.warn(
            exceptions.DataModelNameMissing(values["prefix"].replace("-", "_")).message,
            category=exceptions.DataModelNameMissing,
            stacklevel=2,
        )
        return values["prefix"].replace("-", "_")

    @validator("data_model_name", always=True)
    def is_data_model_name_compliant(cls, value):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("data_model_name", value).to_pydantic_custom_error()
        if not re.match(data_model_id_compliance_regex, value):
            raise exceptions.DataModelNameRegexViolation(
                value, data_model_id_compliance_regex
            ).to_pydantic_custom_error()
        else:
            return value

    @validator("version", always=True)
    def is_version_compliant(cls, value):
        # turn "." into "_" to avoid issues with CDF
        if "." in value:
            warnings.warn(
                exceptions.VersionDotsConvertedToUnderscores().message,
                category=exceptions.VersionDotsConvertedToUnderscores,
                stacklevel=2,
            )
            value = value.replace(".", "_")
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("version", value).to_pydantic_custom_error()
        if not re.match(version_compliance_regex, value):
            raise exceptions.VersionRegexViolation(value, version_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @field_validator("creator", "contributor", mode="before")
    def to_list_if_comma(cls, value, info):
        if isinstance(value, str):
            if value:
                return value.replace(", ", ",").split(",")
            if cls.model_fields[info.field_name].default is None:
                return None
        return value

    def to_pandas(self) -> pd.Series:
        """Converts Metadata to pandas Series."""
        return pd.Series(self.model_dump())

    def _repr_html_(self) -> str:
        """Returns HTML representation of Metadata."""
        return self.to_pandas().to_frame("value")._repr_html_()  # type: ignore[operator]


class Resource(RuleModel):
    """
    Base class for resources that constitute data model (i.e., classes, properties)

    Args:
        description: The description of the resource.
        cdf_resource_type: The CDF resource type to which resource resolves to
        deprecated: Whether the resource is deprecated or not.
        deprecation_date: The date when the resource was deprecated.
        replaced_by: The resource that replaced this resource.
        source: Source of information for given resource
        source_entity_name: The name of the source entity that is closest to the resource being described.
        match_type: The match type of the resource being described and the source entity.
        comment: Additional comment about mapping between the resource being described and the source entity.

    """

    # Solution model
    description: Description | None = Field(alias="Description", default=None)

    # Solution CDF resource, it is not needed when working with FDM, this is only for
    # Classic CDF data model
    cdf_resource_type: list[str] | str | None = Field(alias="Resource Type", default=None)

    # Advance data modeling: Keeping track if Resource got deprecated or not
    deprecated: bool = Field(default=False)
    deprecation_date: datetime | None = Field(alias="deprecationDate", default=None)
    replaced_by: str | None = Field(alias="replacedBy", default=None)

    # Advance data modeling: Relation to existing resources for purpose of mapping
    source: HttpUrl | None = Field(
        alias="Source",
        description=(
            "Source of information for given entity, e.g. https://www.entsoe.eu/digital/common-information-model/"
        ),
        default=None,
    )
    source_entity_name: str | None = Field(
        alias="Source Entity Name", description="Closest entity in source, e.g. Substation", default=None
    )
    match_type: str | None = Field(
        alias="Match Type", description="Type of match between source entity and one being defined", default=None
    )
    comment: str | None = Field(alias="Comment", description="Comment about mapping", default=None)

    @model_validator(mode="before")
    def replace_float_nan_with_default(cls, values: dict) -> dict:
        return replace_nan_floats_with_default(values, cls.model_fields)


T_Resource = TypeVar("T_Resource", bound=Resource)


class ResourceDict(BaseModel, Generic[T_Resource]):
    data: dict[str, T_Resource] = Field(default_factory=dict)

    def __getitem__(self, item: str) -> T_Resource:
        return self.data[item]

    def __setitem__(self, key: str, value: T_Resource):
        self.data[key] = value

    def __contains__(self, item: str) -> bool:
        return item in self.data

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self) -> Iterator[str]:  # type: ignore[override]
        return iter(self.data)

    def values(self) -> ValuesView[T_Resource]:
        return self.data.values()

    def keys(self) -> KeysView[str]:
        return self.data.keys()

    def items(self) -> ItemsView[str, T_Resource]:
        return self.data.items()

    def to_pandas(self, drop_na_columns: bool = True, include: list[str] | None = None) -> pd.DataFrame:
        """Converts ResourceDict to pandas DataFrame."""
        df = pd.DataFrame([class_.model_dump() for class_ in self.data.values()])
        if drop_na_columns:
            df = df.dropna(axis=1, how="all")
        if include is not None:
            df = df[include]
        return df

    def groupby(self, by: str) -> dict[str, ResourceDict[T_Resource]]:
        """Groups ResourceDict by given column(s)."""
        groups: dict[str, ResourceDict[T_Resource]] = {}
        for key, resource in self.data.items():
            value = getattr(resource, by)
            if value not in groups:
                groups[value] = ResourceDict()
            groups[value][key] = resource
        return groups

    def _repr_html_(self) -> str:
        """Returns HTML representation of ResourceDict."""
        return self.to_pandas(drop_na_columns=True)._repr_html_()  # type: ignore[operator]


class Class(Resource):
    """
    Base class for all classes that are part of the data model.

    Args:
        class_id: The class ID of the class.
        class_name: The name of the class.
        parent_class: The parent class of the class.
        parent_asset: The parent asset of the class.
    """

    class_id: ExternalId = Field(alias="Class", min_length=1, max_length=255)
    class_name: ExternalId | None = Field(alias="Name", default=None, min_length=1, max_length=255)
    # Solution model
    parent_class: ExternalId | list[ExternalId] | None = Field(
        alias="Parent Class", default=None, min_length=1, max_length=255
    )

    # Solution CDF resource
    parent_asset: ExternalId | None = Field(alias="Parent Asset", default=None, min_length=1, max_length=255)

    @model_validator(mode="before")
    def replace_nan_floats_with_default(cls, values: dict) -> dict:
        return replace_nan_floats_with_default(values, cls.model_fields)

    @validator("class_id", always=True)
    def is_class_id_compliant(cls, value):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("class_id", value).to_pydantic_custom_error()
        if not re.match(class_id_compliance_regex, value):
            raise exceptions.ClassSheetClassIDRegexViolation(
                value, class_id_compliance_regex
            ).to_pydantic_custom_error()
        else:
            return value

    @validator("class_name", always=True)
    def set_class_name_if_none(cls, value, values):
        if value is None:
            if "class_id" not in values:
                raise exceptions.ClassIDMissing().to_pydantic_custom_error()
            warnings.warn(
                exceptions.ClassNameNotProvided(values["class_id"]).message,
                category=exceptions.ClassNameNotProvided,
                stacklevel=2,
            )
            value = values["class_id"]
        return value

    @field_validator("parent_class", mode="before")
    def to_list_if_comma(cls, value, info):
        if isinstance(value, str):
            if value:
                return value.replace(", ", ",").split(",")
            if cls.model_fields[info.field_name].default is None:
                return None

    @field_validator("parent_class", mode="after")
    def is_parent_class_id_compliant(cls, value):
        if isinstance(value, str):
            if re.search(more_than_one_none_alphanumerics_regex, value):
                raise exceptions.MoreThanOneNonAlphanumericCharacter("parent_class", value).to_pydantic_custom_error()
            if not re.match(class_id_compliance_regex, value):
                raise exceptions.ClassSheetParentClassIDRegexViolation(
                    [value], class_id_compliance_regex
                ).to_pydantic_custom_error()
        elif isinstance(value, list):
            if illegal_ids := [v for v in value if re.search(more_than_one_none_alphanumerics_regex, v)]:
                raise exceptions.MoreThanOneNonAlphanumericCharacter(
                    "parent_class", ", ".join(illegal_ids)
                ).to_pydantic_custom_error()
            if illegal_ids := [v for v in value if not re.match(class_id_compliance_regex, v)]:
                raise exceptions.ClassSheetParentClassIDRegexViolation(
                    illegal_ids, class_id_compliance_regex
                ).to_pydantic_custom_error()
        return value


class Classes(ResourceDict[Class]):
    """This represents a collection of classes that are part of the data model."""

    ...


class Property(Resource):
    """
    A property is a characteristic of a class. It is a named attribute of a class that describes a range of values
    or a relationship to another class.

    Args:
        class_id: Class ID to which property belongs
        property_id: Property ID of the property
        property_name: Property name. Defaults to property_id
        expected_value_type: Expected value type of the property
        min_count: Minimum count of the property values. Defaults to 0
        max_count: Maximum count of the property values. Defaults to None
        default: Default value of the property
        property_type: Property type (DatatypeProperty/attribute or ObjectProperty/edge/relationship)
        cdf_resource_type: CDF resource to under which property will be resolved to (e.g., Asset)
        resource_type_property: To what property of CDF resource given property resolves to (e.g., Asset name)
        source_type: In case if property resolves as CDF relationship, this argument indicates
                     relationship source type (defaults to Asset)
        target_type: In case if property resolves as CDF relationship, this argument
                     indicates relationship target type (defaults to Asset)
        label: CDF Label used for relationship. Defaults to property_id
        relationship_external_id_rule: Rule to use when generating CDF relationship externalId
        rule_type: Rule type for the transformation from source to target representation
                   of knowledge graph. Defaults to None (no transformation)
        rule: Actual rule for the transformation from source to target representation of
              knowledge graph. Defaults to None (no transformation)
        skip_rule: Flag indicating if rule should be skipped when performing
                   knowledge graph transformations. Defaults to False

    """

    # Solution model
    class_id: ExternalId = Field(alias="Class", min_length=1, max_length=255)
    property_id: ExternalId = Field(alias="Property", min_length=1, max_length=255)
    property_name: ExternalId | None = Field(alias="Name", default=None, min_length=1, max_length=255)
    expected_value_type: ExternalId = Field(alias="Type", min_length=1, max_length=255)
    min_count: int | None = Field(alias="Min Count", default=0)
    max_count: int | None = Field(alias="Max Count", default=None)
    default: Any | None = Field(alias="Default", default=None)

    # OWL property
    property_type: str = "DatatypeProperty"

    # Solution CDF resource
    resource_type_property: list[str] | None = Field(alias="Resource Type Property", default=None)
    source_type: str = Field(alias="Relationship Source Type", default="Asset")
    target_type: str = Field(alias="Relationship Target Type", default="Asset")
    label: str | None = Field(alias="Relationship Label", default=None)
    relationship_external_id_rule: str | None = Field(alias="Relationship ExternalID Rule", default=None)

    # Transformation rule (domain to solution)
    rule_type: TransformationRuleType | None = Field(alias="Rule Type", default=None)
    rule: str | AllReferences | SingleProperty | Hop | RawLookup | SPARQLQuery | Traversal | None = Field(
        alias="Rule", default=None
    )
    skip_rule: bool = Field(alias="Skip", default=False)

    # Specialization of cdf_resource_type to allow definition of both
    # Asset and Relationship at the same time
    cdf_resource_type: list[str] = Field(alias="Resource Type", default_factory=list)

    @property
    def is_raw_lookup(self) -> bool:
        return self.rule_type == TransformationRuleType.rawlookup

    @model_validator(mode="before")
    def replace_float_nan_with_default(cls, values: dict) -> dict:
        return replace_nan_floats_with_default(values, cls.model_fields)

    @validator("class_id", always=True)
    def is_class_id_compliant(cls, value):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("class_id", value).to_pydantic_custom_error()
        if not re.match(class_id_compliance_regex, value):
            raise exceptions.PropertiesSheetClassIDRegexViolation(
                value, class_id_compliance_regex
            ).to_pydantic_custom_error()
        else:
            return value

    @validator("property_id", always=True)
    def is_property_id_compliant(cls, value):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("property_id", value).to_pydantic_custom_error()
        if not re.match(property_id_compliance_regex, value):
            raise exceptions.PropertyIDRegexViolation(value, property_id_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("expected_value_type", always=True)
    def is_expected_value_type_compliant(cls, value):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter(
                "expected_value_type", value
            ).to_pydantic_custom_error()
        if not re.match(class_id_compliance_regex, value):
            raise exceptions.ValueTypeIDRegexViolation(value, class_id_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("rule_type", pre=True)
    def to_lowercase(cls, value):
        return value.casefold() if value else value

    @validator("skip_rule", pre=True)
    def from_string(cls, value):
        if isinstance(value, str):
            return value.casefold() in {"true", "skip", "yes", "y"}
        return value

    @validator("rule")
    def is_valid_rule(cls, value, values):
        if rule_type := values.get("rule_type"):
            if not value:
                raise exceptions.RuleTypeProvidedButRuleMissing(
                    values["property_id"], values["class_id"], values["rule_type"]
                ).to_pydantic_custom_error()
            _ = parse_rule(value, rule_type)
        return value

    @validator("resource_type_property", pre=True)
    def split_str(cls, v):
        if v:
            return [v.strip() for v in v.split(",")] if "," in v else [v]

    @field_validator("cdf_resource_type", mode="before")
    def to_list_if_comma(cls, value, info):
        if isinstance(value, str):
            if value:
                return value.replace(", ", ",").split(",")
            if cls.model_fields[info.field_name].default is None:
                return None
        return value

    # Setters
    # TODO: configure setters to only run if field_validators are successful, otherwise do not run them!
    @property
    def is_mandatory(self) -> bool:
        return self.min_count != 0

    @model_validator(mode="after")
    def set_property_type(self):
        if self.expected_value_type in DATA_TYPE_MAPPING.keys():
            self.property_type = "DatatypeProperty"
        else:
            self.property_type = "ObjectProperty"
        return self

    @model_validator(mode="after")
    def set_property_name_if_none(self):
        if self.property_name is None:
            warnings.warn(
                exceptions.PropertyNameNotProvided(self.property_id).message,
                category=exceptions.PropertyNameNotProvided,
                stacklevel=2,
            )
            self.property_name = self.property_id
        return self

    @model_validator(mode="after")
    def set_relationship_label(self):
        if self.label is None:
            warnings.warn(
                exceptions.MissingLabel(self.property_id).message, category=exceptions.MissingLabel, stacklevel=2
            )
            self.label = self.property_id
        return self

    @model_validator(mode="after")
    def set_skip_rule(self):
        if self.rule_type is None:
            warnings.warn(
                exceptions.NoTransformationRules(class_id=self.class_id, property_id=self.property_id).message,
                category=exceptions.NoTransformationRules,
                stacklevel=2,
            )
            self.skip_rule = True
        else:
            self.skip_rule = False
        return self

    @model_validator(mode="after")
    def set_default_as_list(self):
        if (
            self.property_type == "DatatypeProperty"
            and self.default
            and self.max_count
            and self.max_count != 1
            and not isinstance(self.default, list)
        ):
            warnings.warn(
                exceptions.DefaultValueNotList(self.property_id).message,
                category=exceptions.DefaultValueNotList,
                stacklevel=2,
            )
            if isinstance(self.default, str):
                if self.default:
                    self.default = self.default.replace(", ", ",").split(",")
                else:
                    self.default = [self.default]
        return self

    @model_validator(mode="after")
    def is_default_value_type_proper(self):
        if self.property_type == "DatatypeProperty" and self.default:
            default_value = self.default[0] if isinstance(self.default, list) else self.default

            if type(default_value) != type_to_target_convention(self.expected_value_type, "python"):
                try:
                    if isinstance(self.default, list):
                        updated_list = []
                        for value in self.default:
                            updated_list.append(type_to_target_convention(self.expected_value_type, "python")(value))
                        self.default = updated_list
                    else:
                        self.default = type_to_target_convention(self.expected_value_type, "python")(self.default)

                    warnings.warn(
                        exceptions.DefaultValueTypeConverted(
                            self.property_id,
                            type(self.default),
                            type_to_target_convention(self.expected_value_type, "python"),
                        ).message,
                        category=exceptions.DefaultValueTypeConverted,
                        stacklevel=2,
                    )
                except Exception:
                    exceptions.DefaultValueTypeNotProper(
                        self.property_id,
                        type(self.default),
                        type_to_target_convention(self.expected_value_type, "python"),
                    )
        return self


class Properties(ResourceDict[Property]):
    """This represents a collection of properties that are part of the data model."""

    ...


class Prefixes(RuleModel):
    """
    Class deals with prefixes used in the data model and data model instances

    Args:
        prefixes: Dict of prefixes
    """

    prefixes: dict[str, Namespace] = PREFIXES


class Instance(RuleModel):
    """
    Class deals with RDF triple that defines data model instances of data, represented
    as a single row in the `Instances` sheet of the Excel file.

    Args:
        instance: URI of the instance
        property_: URI of the property
        value: value of the property
        namespace: namespace of the instance
        prefixes: prefixes of the instance

    !!! note "Warning"
        Use of the `Instances` sheet is not recommended, instead if you need additional
        triples in your graph use Graph Capturing Sheet instead!

        See
        [`extract_graph_from_sheet`](../graph/extractors.md#cognite.neat.graph.extractors.extract_graph_from_sheet)
        for more details.
    """

    instance: URIRef | None = Field(alias="Instance", default=None)
    property_: URIRef | None = Field(alias="Property", default=None)
    value: Literal | URIRef | None = Field(alias="Value", default=None)
    namespace: Namespace
    prefixes: dict[str, Namespace]

    @staticmethod
    def get_value(value, prefixes) -> URIRef | Literal:
        try:
            url = URL(url=value).url
            return URIRef(str(url))
        except ValidationError:
            try:
                entity = Entity.from_string(value)
                return URIRef(prefixes[entity.prefix][entity.name])
            except ValueError:
                return value

    @model_validator(mode="before")
    def convert_values(cls, values: dict):
        # we expect to read Excel sheet which contains naming convention of column
        # 'Instance', 'Property', 'Value', if that's not the case we should raise error
        if not {"Instance", "Property", "Value"}.issubset(set(values.keys())):
            raise TypeError("We only support inputs from the transformation rule Excel sheet!!!")

        namespace = values["namespace"]
        prefixes = values["prefixes"]

        values["Instance"] = cls.get_value(values["Instance"], prefixes)
        values["Instance"] = (
            values["Instance"] if isinstance(values["Instance"], URIRef) else URIRef(namespace[values["Instance"]])
        )

        values["Property"] = cls.get_value(values["Property"], prefixes)
        values["Property"] = (
            values["Property"] if isinstance(values["Property"], URIRef) else URIRef(namespace[values["Property"]])
        )

        if isinstance(values["Value"], str):
            values["Value"] = cls.get_value(values["Value"], prefixes)
            if not isinstance(values["Value"], URIRef):
                datatype = (
                    XSD.integer
                    if cls.isint(values["Value"])
                    else XSD.float
                    if cls.isfloat(values["Value"])
                    else XSD.string
                )
                values["Value"] = Literal(values["Value"], datatype=datatype)
        elif isinstance(values["Value"], float):
            values["Value"] = Literal(values["Value"], datatype=XSD.float)
        elif isinstance(values["Value"], int):
            values["Value"] = Literal(values["Value"], datatype=XSD.integer)
        elif isinstance(values["Value"], bool):
            values["Value"] = Literal(values["Value"], datatype=XSD.boolean)
        elif isinstance(values["Value"], datetime):
            values["Value"] = Literal(values["Value"], datatype=XSD.dateTime)
        else:
            values["Value"] = Literal(values["Value"], datatype=XSD.string)

        return values

    @staticmethod
    def isfloat(x):
        try:
            _ = float(x)
        except (TypeError, ValueError):
            return False
        else:
            return True

    @staticmethod
    def isint(x):
        try:
            a = float(x)
            b = int(a)
        except (TypeError, ValueError):
            return False
        else:
            return a == b


class Rules(RuleModel):
    """
    Rules is a core concept in `neat`. This represents fusion of data model
    definitions and (optionally) the transformation rules used to transform the data/graph
    from the source representation to the target representation defined by the data model.
    The rules are defined in a Excel sheet and then parsed into a `Rules` object. The
    `Rules` object is then used to generate data model and the`RDF` graph made of data
    model instances.

    Args:
        metadata: Data model metadata
        classes: Classes defined in the data model
        properties: Class properties defined in the data model with accompanying transformation rules
                    to transform data from source to target representation
        prefixes: Prefixes used in the data model. Defaults to PREFIXES
        instances: Instances defined in the data model. Defaults to None
        validators_to_skip: List of validators to skip. Defaults to []

    !!! note "Importers"
        Neat supports importing data from different sources. See the importers section for more details.

    !!! note "Exporters"
        Neat supports exporting data to different sources. See the exporters section for more details.

    !!! note "validators_to_skip" use this only if you are sure what you are doing
    """

    validators_to_skip: list[str] = Field(default_factory=list, exclude=True)
    metadata: Metadata
    classes: Classes
    properties: Properties
    prefixes: dict[str, Namespace] = PREFIXES.copy()
    instances: list[Instance] = Field(default_factory=list)

    @property
    def raw_tables(self) -> list[str]:
        return list(
            {
                parse_rule(rule.rule, TransformationRuleType.rawlookup).table.name  # type: ignore[arg-type, attr-defined]
                for rule in self.properties.values()
                if rule.is_raw_lookup
            }
        )

    @field_validator("instances", mode="before")
    def none_as_empty_list(cls, value):
        if value is None:
            return []
        return value

    @field_validator("classes", mode="before")
    def dict_to_classes_obj(cls, value: dict | Classes) -> Classes:
        if not isinstance(value, dict):
            return value
        dict_of_classes = TypeAdapter(dict[str, Class]).validate_python(value)
        return Classes(data=dict_of_classes)

    @field_validator("properties", mode="before")
    def dict_to_properties_obj(cls, value: dict | Properties) -> Properties:
        if not isinstance(value, dict):
            return value
        dict_of_properties = TypeAdapter(dict[str, Property]).validate_python(value)
        return Properties(data=dict_of_properties)

    @model_validator(mode="after")
    def properties_refer_existing_classes(self) -> Self:
        errors = []

        if cast(FrameType, inspect.currentframe()).f_code.co_name in self.validators_to_skip:
            return self

        for property_ in self.properties.values():
            if property_.class_id not in self.classes:
                errors.append(
                    exceptions.PropertyDefinedForUndefinedClass(
                        property_.property_id, property_.class_id
                    ).to_pydantic_custom_error()
                )
            if property_.property_type == "ObjectProperty" and property_.expected_value_type not in self.classes:
                errors.append(
                    exceptions.ValueTypeNotDefinedAsClass(
                        property_.class_id, property_.property_id, property_.expected_value_type
                    ).to_pydantic_custom_error()
                )
        if errors:
            raise exceptions.MultipleExceptions(errors)
        return self

    @validator("properties")
    def is_type_defined_as_object(cls, value, values):
        if inspect.currentframe().f_code.co_name in values["validators_to_skip"]:
            return value

        defined_objects = {property_.class_id for property_ in value.values()}

        if undefined_objects := [
            property_.expected_value_type
            for _, property_ in value.items()
            if property_.property_type == "ObjectProperty" and property_.expected_value_type not in defined_objects
        ]:
            raise exceptions.UndefinedObjectsAsExpectedValueTypes(undefined_objects).to_pydantic_custom_error()
        else:
            return value

    @validator("prefixes")
    def are_prefixes_compliant(cls, value):
        if ill_formed_prefixes := [
            prefix for prefix, _ in value.items() if re.search(more_than_one_none_alphanumerics_regex, prefix)
        ]:
            raise exceptions.MoreThanOneNonAlphanumericCharacter(
                "prefixes", ", ".join(ill_formed_prefixes)
            ).to_pydantic_custom_error()
        if ill_formed_prefixes := [
            prefix for prefix, _ in value.items() if not re.match(prefix_compliance_regex, prefix)
        ]:
            raise exceptions.PrefixesRegexViolation(
                ill_formed_prefixes, prefix_compliance_regex
            ).to_pydantic_custom_error()
        else:
            return value

    @validator("prefixes")
    def are_namespaces_compliant(cls, value):
        ill_formed_namespaces = []
        for _, namespace in value.items():
            try:
                _ = URL(url=namespace).url
            except ValueError:
                ill_formed_namespaces += namespace

        if ill_formed_namespaces:
            raise exceptions.PrefixesSheetNamespaceNotValidURL(ill_formed_namespaces).to_pydantic_custom_error()
        else:
            return value

    @validator("prefixes")
    def add_data_model_prefix_namespace(cls, value, values):
        if "metadata" not in values:
            raise exceptions.MetadataSheetMissingOrFailedValidation().to_pydantic_custom_error()
        if "prefix" not in values["metadata"].dict():
            raise exceptions.FiledInMetadataSheetMissingOrFailedValidation(
                missing_field="prefix"
            ).to_pydantic_custom_error()
        if "namespace" not in values["metadata"].dict():
            raise exceptions.FiledInMetadataSheetMissingOrFailedValidation(
                missing_field="namespace"
            ).to_pydantic_custom_error()

        value[values["metadata"].prefix] = values["metadata"].namespace
        return value

    def _repr_html_(self) -> str:
        """Pretty display of the TransformationRules object in a Notebook"""
        dump = self.metadata.model_dump()
        for key in ["creator", "contributor"]:
            dump[key] = ", ".join(dump[key]) if isinstance(dump[key], list) else dump[key]
        dump["class_count"] = len(self.classes)
        dump["property_count"] = len(self.properties)
        dump["instance_count"] = len(self.instances)
        return pd.Series(dump).to_frame("value")._repr_html_()  # type: ignore[operator]
