"""This module contains the definition of `TransformationRules` pydantic model and all
its sub-models and validators.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime
from functools import wraps
from collections.abc import ItemsView, Iterator, KeysView, ValuesView
from typing import Any, ClassVar, Generic, TypeAlias, TypeVar, cast

import pandas as pd
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    constr,
)
from pydantic.fields import FieldInfo
from rdflib import Namespace

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum

from cognite.neat.rules.models.value_types import ValueType
from cognite.neat.rules.models._base import (
    ParentClass,
)

from cognite.neat.rules.models.rdfpath import (
    AllReferences,
    Hop,
    RawLookup,
    SingleProperty,
    SPARQLQuery,
    TransformationRuleType,
    Traversal,
)

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


########################################################################################
### These highly depend on CDF API endpoint limitations we need to keep them updated ###
########################################################################################
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
Space: TypeAlias = str
Description: TypeAlias = constr(min_length=1, max_length=1024)  # type: ignore[valid-type]


class RoleTypes(StrEnum):
    domain_expert = "domain expert"
    information_architect = "information architect"
    cdf_solution_architect = "cdf solution architect"


class MatchType(StrEnum):
    exact = "exact"
    partial = "partial"


class RuleModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=True,
        strict=False,
        extra="allow",
        use_enum_values=True,
    )
    validators_to_skip: set[str] = Field(default_factory=set, exclude=True)

    @classmethod
    def mandatory_fields(cls, use_alias=False) -> set[str]:
        """Returns a set of mandatory fields for the model."""
        return _get_required_fields(cls, use_alias)


class URL(BaseModel):
    url: HttpUrl


T_Resource = TypeVar("T_Resource", bound=RuleModel)


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


class CoreMetadata(RuleModel):
    """
    Metadata model for data model

    """

    role: RoleTypes | None = Field(description=("Role of the person who creates the data model"), default=None)

    prefix: Prefix | None = Field(
        description=("This is used as a short form for namespace"),
        default=None,
    )

    namespace: Namespace | None = Field(
        description="This is used as RDF namespace for generation of semantic data model representation",
        min_length=1,
        max_length=2048,
        default=None,
    )

    space: Space | None = Field(
        description=("CDF space to which data model is suppose to be stored under"),
        default=None,
    )

    externalId: ExternalId | None = Field(
        description=("Data model external id when resolving rules as CDF data model"),
        default=None,
        min_length=1,
        max_length=255,
    )

    version: str | None = Field(
        description=("Data model version"),
        min_length=1,
        max_length=43,
        default=None,
    )

    name: str | None = Field(
        alias="title",
        description=("Human readable name of the data model"),
        min_length=1,
        max_length=255,
        default=None,
    )

    description: Description | None = Field(
        description=("Description/definition of the data model"),
        default=None,
    )

    created: datetime | None = Field(
        description=("Date of the data model creation"),
        default=None,
    )

    updated: datetime | None = Field(
        description=("Date of the data model update"),
        default=None,
    )

    creator: str | list[str] | None = Field(
        description=("Creator(s) of the data model"),
        default=None,
    )

    contributor: str | list[str] | None = Field(
        description=("Contributor(s) of the data model"),
        default=None,
    )

    rights: str | None = Field(
        description=("Usage rights of the data model"),
        default=None,
    )

    license: str | None = Field(
        description=("License of the data model"),
        default=None,
    )

    def to_pandas(self) -> pd.Series:
        """Converts Metadata to pandas Series."""
        return pd.Series(self.model_dump())

    def _repr_html_(self) -> str:
        """Returns HTML representation of Metadata."""
        return self.to_pandas().to_frame("value")._repr_html_()  # type: ignore[operator]


class CoreProperty(RuleModel):
    """
    A property is a characteristic of a class. It is a named attribute of a class that describes a range of values
    or a relationship to another class.

    Args:
        class_id: Class ID to which property belongs
        property_id: Property ID of the property
        property_name: Property name. Defaults to property_id
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

    class_id: ExternalId = Field(alias="Class", min_length=1, max_length=255)
    property_id: ExternalId = Field(alias="Property", min_length=1, max_length=255)
    property_name: ExternalId | None = Field(alias="Name", default=None, min_length=1, max_length=255)
    value_type: ValueType = Field(alias="Value Type")
    min_count: int | None = Field(alias="Min Count", default=None)
    max_count: int | None = Field(alias="Max Count", default=None)
    default: Any | None = Field(alias="Default", default=None)
    source: Namespace | None = None
    match_type: MatchType | None = None
    rule_type: TransformationRuleType | None = Field(alias="Rule Type", default=None)
    rule: str | AllReferences | SingleProperty | Hop | RawLookup | SPARQLQuery | Traversal | None = Field(
        alias="Rule", default=None
    )


class CoreProperties(ResourceDict[CoreProperty]):
    """This represents a collection of properties that are part of the data model."""

    ...


class CoreClass(RuleModel):
    """
    Base class for all classes that are part of the data model.

    Args:
        class_id: The class ID of the class.
        class_name: The name of the class.
        parent_class: The parent class of the class.
        source: Source of information for given resource
        match_type: The match type of the resource being described and the source entity.
    """

    class_id: ExternalId = Field(alias="Class", min_length=1, max_length=255)
    class_name: ExternalId | None = Field(alias="Name", min_length=1, max_length=255, default=None)
    parent_class: list[ParentClass] | None = Field(alias="Parent Class", default=None)
    source: Namespace | None = None
    match_type: MatchType | None = None


class CoreClasses(ResourceDict[CoreClass]):
    """This represents a collection of classes that are part of the data model."""

    ...


class CoreRules(RuleModel):
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
    """

    metadata: CoreMetadata
    properties: CoreProperties
    classes: CoreClasses
