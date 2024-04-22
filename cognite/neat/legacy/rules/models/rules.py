"""This module contains the definition of `TransformationRules` pydantic model and all
its sub-models and validators.
"""

from __future__ import annotations

import math
import re
import sys
import warnings
from collections.abc import ItemsView, Iterator, KeysView, ValuesView
from datetime import datetime
from functools import wraps
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
    validator,
)
from pydantic.fields import FieldInfo
from rdflib import XSD, Literal, Namespace, URIRef

from cognite.neat.constants import PREFIXES
from cognite.neat.legacy.rules import exceptions
from cognite.neat.legacy.rules.models._base import (
    ENTITY_ID_REGEX_COMPILED,
    VERSIONED_ENTITY_REGEX_COMPILED,
    ContainerEntity,
    EntityTypes,
    ParentClass,
)
from cognite.neat.legacy.rules.models.rdfpath import (
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
from cognite.neat.legacy.rules.models.value_types import XSD_VALUE_TYPE_MAPPINGS, ValueType

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
            output[field_name] = value.strip() if isinstance(value, str) else value
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
                output[field_name] = value.strip() if isinstance(value, str) else value
    return output


def skip_field_validator(validators_field):
    def decorator(func):
        @wraps(func)
        def wrapper(cls, value, values):
            if isinstance(values, dict):
                to_skip = values.get(validators_field, set())
            else:
                try:
                    to_skip = values.data.get(validators_field, set())
                except Exception:
                    to_skip = set()

            if "all" in to_skip or func.__name__ in to_skip:
                return value
            return func(cls, value, values)

        return wrapper

    return decorator


def skip_model_validator(validators_field):
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            to_skip = getattr(self, validators_field, set())
            if "all" in to_skip or func.__name__ in to_skip:
                return self

            return func(self)

        return wrapper

    return decorator


class RuleModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=True,
        strict=False,
        extra="allow",
    )
    validators_to_skip: set[str] = Field(default_factory=set, exclude=True)

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


########################################################################################
### These highly depend on CDF API endpoint limitations we need to keep them updated ###
########################################################################################
Description: TypeAlias = constr(min_length=1, max_length=1024)  # type: ignore[valid-type]

more_than_one_none_alphanumerics_regex = r"([_-]{2,})"

prefix_compliance_regex = r"^([a-zA-Z]+)([a-zA-Z0-9]*[_-]{0,1}[a-zA-Z0-9_-]*)([a-zA-Z0-9]*)$"
data_model_id_compliance_regex = r"^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$"
cdf_space_compliance_regex = (
    r"(?!^(space|cdf|dms|pg3|shared|system|node|edge)$)(^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$)"
)

view_id_compliance_regex = (
    r"(?!^(Query|Mutation|Subscription|String|Int32|Int64|Int|Float32|Float64|Float|"
    r"Timestamp|JSONObject|Date|Numeric|Boolean|PageInfo|File|Sequence|TimeSeries)$)"
    r"(^[a-zA-Z][a-zA-Z0-9_]{0,253}[a-zA-Z0-9]?$)"
)

value_id_compliance_regex = r"(^[a-zA-Z][a-zA-Z0-9_]{0,253}[a-zA-Z0-9]?$)"

dms_property_id_compliance_regex = (
    r"(?!^(space|externalId|createdTime|lastUpdatedTime|deletedTime|edge_id|"
    r"node_id|project_id|property_group|seq|tg_table_name|extensions)$)"
    r"(^[a-zA-Z][a-zA-Z0-9_]{0,253}[a-zA-Z0-9]?$)"
)


class_id_compliance_regex = r"(?!^(Class|class)$)(^[a-zA-Z][a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]?$)"
property_id_compliance_regex = r"^(\*)|(?!^(Property|property)$)(^[a-zA-Z][a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]?$)"

version_compliance_regex = r"^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$"
########################################################################################
########################################################################################


Prefix: TypeAlias = str
ExternalId: TypeAlias = str


class Metadata(RuleModel):
    """
    Metadata model for data model

    Args:
        prefix: This is used as prefix for generation of RDF OWL/SHACL data model representation
        suffix: Suffix is used as the data model external id when resolving rules as CDF data model
        namespace: This is used as RDF namespace for generation of RDF OWL/SHACL data model representation and/or for
                   generation of RDF graphs
        title: This is used as data model name in CDF, or as a data model title in RDF
        version: This is used as RDF and CDF data model version
        created: This is used as RDF data model creation date for generation of RDF OWL/SHACL data model representation
        updated: This is used as RDF data model update date for generation of RDF OWL/SHACL data model representation
        description: This is used as RDF data model description for generation of RDF
                     OWL/SHACL data model representation
        creator: This is used as RDF data model creator for generation of RDF OWL/SHACL data model representation
        contributor: This is used as RDF data model contributor for generation of
                     RDF OWL/SHACL data model representation
        rights: This is used as RDF data model rights for generation of RDF OWL/SHACL data model representation
    """

    prefix: Prefix = Field(
        alias="space",
        description=(
            "This is used as prefix for generation of RDF OWL/SHACL data model representation"
            " and/or as CDF space name to which model is intend to be stored"
        ),
    )

    suffix: ExternalId | None = Field(
        description=(
            "Suffix is used as the data model external id when resolving rules as CDF data model"
            " This field is optional and if not provided it will be generated from prefix."
        ),
        alias="external_id",
        default=None,
        min_length=1,
        max_length=255,
    )

    namespace: Namespace | None = Field(
        description="This is used as RDF namespace for generation of RDF OWL/SHACL data model representation "
        "and/or for generation of RDF graphs.",
        min_length=1,
        max_length=2048,
        default=None,
    )

    version: str = Field(min_length=1, max_length=43)
    title: str | None = Field(alias="name", min_length=1, max_length=255, default=None)

    description: Description | None = None

    created: datetime = Field(default_factory=lambda: datetime.utcnow())
    updated: datetime = Field(default_factory=lambda: datetime.utcnow())

    creator: str | list[str] | None = None
    contributor: str | list[str] | None = None
    rights: str | None = "Restricted for Internal Use of Cognite"
    license: str | None = "Proprietary License"

    @field_validator("contributor", "contributor", "description", "rights", mode="before")
    def replace_float_nan_with_default(cls, value, info):
        if isinstance(value, float) and math.isnan(value):
            return cls.model_fields[info.field_name].default
        return value

    @field_validator("version", mode="before")
    def convert_to_string(cls, value):
        return str(value)

    @validator("prefix", always=True)
    @skip_field_validator("validators_to_skip")
    def is_prefix_compliant(cls, value, values):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("prefix", value).to_pydantic_custom_error()
        if not re.match(cdf_space_compliance_regex, value):
            raise exceptions.PrefixRegexViolation(value, cdf_space_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("suffix", always=True)
    @skip_field_validator("validators_to_skip")
    def set_suffix_if_none(cls, value, values):
        if value is not None:
            return value
        warnings.warn(
            exceptions.DataModelIdMissing(values["prefix"].replace("-", "_")).message,
            category=exceptions.DataModelIdMissing,
            stacklevel=2,
        )
        return values["prefix"].replace("-", "_")

    @validator("suffix", always=True)
    @skip_field_validator("validators_to_skip")
    def is_suffix_compliant(cls, value, values):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("suffix", value).to_pydantic_custom_error()
        if not re.match(data_model_id_compliance_regex, value):
            raise exceptions.DataModelIdRegexViolation(value, data_model_id_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("namespace", always=True)
    @skip_field_validator("validators_to_skip")
    def set_namespace_if_none(cls, value, values):
        if value is None:
            suffix = f"/{values['suffix']}" if values["prefix"] != values["suffix"] else ""
            return Namespace(f"http://purl.org/cognite/{values['prefix']}{suffix}#")
        try:
            return Namespace(TypeAdapter(HttpUrl).validate_python(value))
        except ValidationError as e:
            raise exceptions.MetadataSheetNamespaceNotValidURL(value).to_pydantic_custom_error() from e

    @validator("namespace", always=True)
    @skip_field_validator("validators_to_skip")
    def fix_namespace_ending(cls, value, values):
        if value.endswith("#") or value.endswith("/"):
            return value
        warnings.warn(
            exceptions.NamespaceEndingFixed(value).message, category=exceptions.NamespaceEndingFixed, stacklevel=2
        )
        return Namespace(f"{value}#")

    @validator("title", always=True)
    @skip_field_validator("validators_to_skip")
    def set_title_if_none(cls, value, values):
        if value is not None:
            return value
        elif values["suffix"]:
            return values["suffix"]
        else:
            return values["prefix"]

    @validator("creator", always=True)
    @skip_field_validator("validators_to_skip")
    def set_creator_if_none(cls, value, values):
        if value is not None:
            return value
        else:
            return ["neat"]

    @validator("contributor", always=True)
    @skip_field_validator("validators_to_skip")
    def set_contributor_if_none(cls, value, values):
        if value is not None:
            return value
        else:
            return ["Cognite"]

    @validator("version", always=True)
    @skip_field_validator("validators_to_skip")
    def is_version_compliant(cls, value, values):
        if not re.match(version_compliance_regex, value):
            raise exceptions.VersionRegexViolation(value, version_compliance_regex).to_pydantic_custom_error()
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

    @property
    def space(self) -> str:
        """Returns data model space."""
        return cast(str, self.prefix)

    @property
    def external_id(self) -> str:
        """Returns data model external."""
        return cast(str, self.suffix)

    @property
    def name(self) -> str:
        """Returns data model name."""
        return cast(str, self.title)

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
    """

    class_id: ExternalId = Field(alias="Class", min_length=1, max_length=255)
    class_name: ExternalId | None = Field(alias="Name", default=None, min_length=1, max_length=255)
    # Solution model
    parent_class: list[ParentClass] | None = Field(alias="Parent Class", default=None)
    # Todo: Remove? Does not seem to be used anywhere
    filter_: str | None = Field(alias="Filter", default=None, min_length=1)

    @model_validator(mode="before")
    def replace_nan_floats_with_default(cls, values: dict) -> dict:
        return replace_nan_floats_with_default(values, cls.model_fields)

    @validator("class_id", always=True)
    @skip_field_validator("validators_to_skip")
    def is_class_id_compliant(cls, value, values):
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
    @skip_field_validator("validators_to_skip")
    def parent_class_to_list_of_entities(cls, value, values):
        if isinstance(value, str) and value:
            parent_classes = []
            for v in value.replace(", ", ",").split(","):
                if ENTITY_ID_REGEX_COMPILED.match(v) or VERSIONED_ENTITY_REGEX_COMPILED.match(v):
                    parent_classes.append(ParentClass.from_string(entity_string=v))
                else:
                    # if all fails defaults "neat" object which ends up being updated to proper
                    # prefix and version upon completion of Rules validation
                    parent_classes.append(ParentClass(prefix="undefined", suffix=v, name=v))

            return parent_classes
        else:
            return None

    @field_validator("parent_class", mode="after")
    @skip_field_validator("validators_to_skip")
    def is_parent_class_id_compliant(cls, value, values):
        if isinstance(value, list):
            if illegal_ids := [v for v in value if re.search(more_than_one_none_alphanumerics_regex, v.suffix)]:
                raise exceptions.MoreThanOneNonAlphanumericCharacter(
                    "parent_class", ", ".join(illegal_ids)
                ).to_pydantic_custom_error()
            if illegal_ids := [v for v in value if not re.match(class_id_compliance_regex, v.suffix)]:
                for v in illegal_ids:
                    print(v.id)
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
    expected_value_type: ValueType = Field(alias="Type")
    min_count: int | None = Field(alias="Min Count", default=0)
    max_count: int | None = Field(alias="Max Count", default=None)
    default: Any | None = Field(alias="Default", default=None)

    # OWL property
    property_type: str = EntityTypes.data_property

    # Core CDF resources (Asset, Relationship, and Labels)
    resource_type_property: list[str] | None = Field(
        alias="Resource Type Property",
        default=None,
        description="This is what property to resolve to in CDF resource, for "
        "example f cdf_resource_type is 'Asset', then this could"
        "be 'name' or 'description'. Note you can specify "
        "multiple properties ['name', 'metadata'] which would store"
        "this property twice in CDF, once as 'name' and once as 'metadata",
    )
    source_type: str = Field(alias="Relationship Source Type", default="Asset")
    target_type: str = Field(alias="Relationship Target Type", default="Asset")
    label: str | None = Field(alias="Relationship Label", default=None)
    relationship_external_id_rule: str | None = Field(alias="Relationship ExternalID Rule", default=None)
    # Specialization of cdf_resource_type to allow definition of both
    # Asset and Relationship at the same time
    cdf_resource_type: list[str] = Field(
        alias="Resource Type", default_factory=list, description="This is typically 'Asset' or 'Relationship'"
    )

    # Transformation rule (domain to solution)
    rule_type: TransformationRuleType | None = Field(alias="Rule Type", default=None)
    rule: str | AllReferences | SingleProperty | Hop | RawLookup | SPARQLQuery | Traversal | None = Field(
        alias="Rule", default=None
    )
    skip_rule: bool = Field(alias="Skip", default=False)

    # Container-specific things, only used for advance modeling or auto-filled by neat
    container: ContainerEntity | None = Field(alias="Container", default=None)
    container_property: str | None = Field(alias="Container Property", default=None)
    index: bool | None = Field(alias="Index", default=False)
    constraints: str | None = Field(alias="Constraints", default=None, min_length=1)

    @property
    def is_raw_lookup(self) -> bool:
        return self.rule_type == TransformationRuleType.rawlookup

    @model_validator(mode="before")
    def replace_float_nan_with_default(cls, values: dict) -> dict:
        return replace_nan_floats_with_default(values, cls.model_fields)

    @field_validator("container", mode="before")
    def container_string_to_entity(cls, value):
        if not value:
            return value

        if ENTITY_ID_REGEX_COMPILED.match(value) or VERSIONED_ENTITY_REGEX_COMPILED.match(value):
            return ContainerEntity.from_string(entity_string=value)
        else:
            return ContainerEntity(prefix="undefined", suffix=value, name=value)

    @field_validator("expected_value_type", mode="before")
    def expected_value_type_string_to_entity(cls, value):
        # handle simple types
        if value in XSD_VALUE_TYPE_MAPPINGS.keys():
            return XSD_VALUE_TYPE_MAPPINGS[value]

        # complex types correspond to relations to other classes
        if ENTITY_ID_REGEX_COMPILED.match(value) or VERSIONED_ENTITY_REGEX_COMPILED.match(value):
            return ValueType.from_string(entity_string=value, type_=EntityTypes.object_value_type, mapping=None)
        else:
            return ValueType(
                prefix="undefined", suffix=value, name=value, type_=EntityTypes.object_value_type, mapping=None
            )
        #     return ValueType(

    @validator("class_id", always=True)
    @skip_field_validator("validators_to_skip")
    def is_class_id_compliant(cls, value, values):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("class_id", value).to_pydantic_custom_error()
        if not re.match(class_id_compliance_regex, value):
            raise exceptions.PropertiesSheetClassIDRegexViolation(
                value, class_id_compliance_regex
            ).to_pydantic_custom_error()
        else:
            return value

    @validator("property_id", always=True)
    @skip_field_validator("validators_to_skip")
    def is_property_id_compliant(cls, value, values):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("property_id", value).to_pydantic_custom_error()
        if not re.match(property_id_compliance_regex, value):
            raise exceptions.PropertyIDRegexViolation(value, property_id_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("expected_value_type", always=True)
    @skip_field_validator("validators_to_skip")
    def is_expected_value_type_compliant(cls, value, values):
        if re.search(more_than_one_none_alphanumerics_regex, value.suffix):
            raise exceptions.MoreThanOneNonAlphanumericCharacter(
                "expected_value_type", value
            ).to_pydantic_custom_error()
        if not re.match(class_id_compliance_regex, value.suffix):
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
    @skip_field_validator("validators_to_skip")
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
        if self.expected_value_type.type_ == EntityTypes.data_value_type:
            self.property_type = EntityTypes.data_property
        else:
            self.property_type = EntityTypes.object_property
        return self

    @model_validator(mode="after")
    def set_container_if_missing(self):
        if not self.container and (
            self.expected_value_type.type_ == EntityTypes.data_value_type or self.max_count == 1
        ):
            self.container = ContainerEntity(prefix="undefined", suffix=self.class_id, name=self.class_id)
        return self

    @model_validator(mode="after")
    def set_container_property_if_missing(self):
        if not self.container_property and (
            self.expected_value_type.type_ == EntityTypes.data_value_type or self.max_count == 1
        ):
            self.container_property = self.property_id
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
    @skip_model_validator("validators_to_skip")
    def set_relationship_label(self):
        if self.label is None:
            warnings.warn(
                exceptions.MissingLabel(self.property_id).message, category=exceptions.MissingLabel, stacklevel=2
            )
            self.label = self.property_id
        return self

    @model_validator(mode="after")
    @skip_model_validator("validators_to_skip")
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
    @skip_model_validator("validators_to_skip")
    def is_default_value_type_proper(self):
        if self.property_type == "DatatypeProperty" and self.default:
            default_value = self.default[0] if isinstance(self.default, list) else self.default

            if type(default_value) != self.expected_value_type.python:
                try:
                    if isinstance(self.default, list):
                        updated_list = []
                        for value in self.default:
                            updated_list.append(self.expected_value_type.python(value))
                        self.default = updated_list
                    else:
                        self.default = self.expected_value_type.python(self.default)

                except Exception:
                    exceptions.DefaultValueTypeNotProper(
                        self.property_id,
                        type(self.default),
                        self.expected_value_type.python,
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
                return URIRef(prefixes[entity.prefix][entity.suffix])
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
    @skip_model_validator("validators_to_skip")
    def update_prefix_version_entities(self) -> Self:
        version = self.metadata.version
        prefix = self.metadata.prefix

        # update expected_value_types
        for id_ in self.properties.keys():
            # only update version of expected value type which are part of this data model
            if (
                not self.properties[id_].expected_value_type.version
                and self.properties[id_].expected_value_type.prefix == "undefined"
            ):
                self.properties[id_].expected_value_type.version = version

            if self.properties[id_].expected_value_type.prefix == "undefined":
                self.properties[id_].expected_value_type.prefix = prefix

        # update container
        for id_ in self.properties.keys():
            # only update version of expected value type which are part of this data model
            if (
                self.properties[id_].container
                and cast(ContainerEntity, self.properties[id_].container).prefix == "undefined"
            ):
                cast(ContainerEntity, self.properties[id_].container).prefix = prefix

        # update parent classes
        for id_ in self.classes.keys():
            if self.classes[id_].parent_class:
                for parent_class in cast(list[ParentClass], self.classes[id_].parent_class):
                    if parent_class.prefix == "undefined":
                        parent_class.prefix = prefix
                    if not parent_class.version:
                        parent_class.version = version

        return self

    @model_validator(mode="after")
    @skip_model_validator("validators_to_skip")
    def update_container_description_and_name(self):
        for id_ in self.properties.keys():
            if (
                self.properties[id_].container
                and self.properties[id_].container.external_id in self.classes
                and self.properties[id_].container.space == self.metadata.space
            ):
                self.properties[id_].container.description = self.classes[
                    self.properties[id_].container.external_id
                ].description

                self.properties[id_].container.name = self.classes[
                    self.properties[id_].container.external_id
                ].class_name
        return self

    @model_validator(mode="after")
    @skip_model_validator("validators_to_skip")
    def add_missing_classes(self):
        for property_ in self.properties.values():
            if property_.class_id not in self.classes:
                self.classes[property_.class_id] = Class(
                    class_id=property_.class_id,
                    class_name=property_.class_id,
                    comment="This class was automatically added by neat",
                )
        return self

    def update_prefix(self, prefix: str):
        if prefix == self.metadata.prefix:
            warnings.warn("Prefix is already in use, no changes made!", stacklevel=2)
        elif prefix in self.prefixes.keys():
            raise exceptions.PrefixAlreadyInUse(prefix).to_pydantic_custom_error()
        elif not re.match(cdf_space_compliance_regex, prefix):
            raise exceptions.PrefixRegexViolation(prefix, cdf_space_compliance_regex).to_pydantic_custom_error()
        else:
            old_prefix = self.metadata.prefix
            self.metadata.prefix = prefix

            # update entity ids for expected_value_types and containers
            for id_ in self.properties.keys():
                if self.properties[id_].expected_value_type.prefix == old_prefix:
                    self.properties[id_].expected_value_type.prefix = prefix

                if (
                    self.properties[id_].container
                    and cast(ContainerEntity, self.properties[id_].container).prefix == old_prefix
                ):
                    cast(ContainerEntity, self.properties[id_].container).prefix = prefix

            # update parent classes
            for id_ in self.classes.keys():
                if self.classes[id_].parent_class:
                    for parent_class in cast(list[ParentClass], self.classes[id_].parent_class):
                        if parent_class.prefix == old_prefix:
                            parent_class.prefix = prefix

            # update prefixes
            self.prefixes[prefix] = self.prefixes.pop(old_prefix)

    def update_space(self, space: str):
        "Convenience method for updating prefix more intuitive to CDF users"
        return self.update_prefix(space)

    def update_version(self, version: str):
        if version == self.metadata.version:
            warnings.warn("Version is already in use, no changes made!", stacklevel=2)
        elif not re.match(version_compliance_regex, version):
            raise exceptions.VersionRegexViolation(version, version_compliance_regex).to_pydantic_custom_error()
        else:
            old_version = self.metadata.version
            self.metadata.version = version
            for id_ in self.properties.keys():
                if (
                    self.properties[id_].expected_value_type.prefix == self.metadata.prefix
                    and self.properties[id_].expected_value_type.version == old_version
                ):
                    self.properties[id_].expected_value_type.version = version

            for id_ in self.classes.keys():
                if self.classes[id_].parent_class:
                    for parent_class in cast(list[ParentClass], self.classes[id_].parent_class):
                        if parent_class.prefix == self.metadata.prefix and parent_class.version == old_version:
                            parent_class.version = version

    @validator("prefixes")
    @skip_field_validator("validators_to_skip")
    def are_prefixes_compliant(cls, value, values):
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
    @skip_field_validator("validators_to_skip")
    def are_namespaces_compliant(cls, value, values):
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
    @skip_field_validator("validators_to_skip")
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

    @property
    def space(self) -> str:
        """Returns data model space."""
        return cast(str, self.metadata.prefix)

    @property
    def external_id(self) -> str:
        """Returns data model external."""
        return cast(str, self.metadata.suffix)

    @property
    def name(self) -> str:
        """Returns data model name."""
        return cast(str, self.metadata.title)

    def _repr_html_(self) -> str:
        """Pretty display of the TransformationRules object in a Notebook"""
        dump = self.metadata.model_dump(by_alias=True)
        for key in ["creator", "contributor"]:
            dump[key] = ", ".join(dump[key]) if isinstance(dump[key], list) else dump[key]
        dump["class_count"] = len(self.classes)
        dump["property_count"] = len(self.properties)
        dump["instance_count"] = len(self.instances)
        return pd.Series(dump).to_frame("value")._repr_html_()  # type: ignore[operator]
