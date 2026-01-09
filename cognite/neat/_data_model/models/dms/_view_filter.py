from abc import ABC
from typing import Annotated, Any, Literal, TypeAlias, get_args

from pydantic import BeforeValidator, Field, JsonValue, TypeAdapter, model_serializer
from pydantic_core.core_schema import FieldSerializationInfo

from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.useful_types import BaseModelObject

from ._references import ContainerReference, NodeReference, ViewReference

# Base classes and helpers


class Parameter(BaseModelObject):
    parameter: str


class FilterDataDefinition(BaseModelObject, ABC):
    """Base class for filter data models."""

    # This is an internal field used for discriminating between filter types. It is not part of the actual
    # data sent to or received from the API. See the _move_filter_key function for more details.
    filter_type: str = Field(..., exclude=True)


class PropertyReference(FilterDataDefinition, ABC):
    """Represents the property path in filters."""

    property: list[str] = Field(..., min_length=2, max_length=3)


## Leaf filters that follows the standard pattern


class EqualsFilterData(PropertyReference):
    filter_type: Literal["equals"] = Field("equals", exclude=True)
    value: JsonValue | PropertyReference


class InFilterData(PropertyReference):
    filter_type: Literal["in"] = Field("in", exclude=True)
    values: list[JsonValue] | PropertyReference


class RangeFilterData(PropertyReference):
    filter_type: Literal["range"] = Field("range", exclude=True)
    gt: str | int | float | PropertyReference | None = None
    gte: str | int | float | PropertyReference | None = None
    lt: str | int | float | PropertyReference | None = None
    lte: str | int | float | PropertyReference | None = None


class PrefixFilterData(PropertyReference):
    filter_type: Literal["prefix"] = Field("prefix", exclude=True)
    value: str | Parameter


class ExistsFilterData(PropertyReference):
    filter_type: Literal["exists"] = Field("exists", exclude=True)


class ContainsAnyFilterData(PropertyReference):
    filter_type: Literal["containsAny"] = Field("containsAny", exclude=True)
    values: list[JsonValue] | PropertyReference


class ContainsAllFilterData(PropertyReference):
    filter_type: Literal["containsAll"] = Field("containsAll", exclude=True)
    values: list[JsonValue] | PropertyReference


class MatchAllFilterData(FilterDataDefinition):
    filter_type: Literal["matchAll"] = Field("matchAll", exclude=True)


class NestedFilterData(FilterDataDefinition):
    filter_type: Literal["nested"] = Field("nested", exclude=True)
    scope: list[str] = Field(..., min_length=1, max_length=3)
    filter: "Filter"


class OverlapsFilterData(PropertyReference):
    filter_type: Literal["overlaps"] = Field("overlaps", exclude=True)
    start_property: list[str] = Field(..., min_length=1, max_length=3)
    end_property: list[str] = Field(..., min_length=1, max_length=3)
    gt: str | int | float | PropertyReference | None = None
    gte: str | int | float | PropertyReference | None = None
    lt: str | int | float | PropertyReference | None = None
    lte: str | int | float | PropertyReference | None = None


class ListFilterDataDefinition(FilterDataDefinition, ABC):
    """Base class for filters that operate on lists of values."""

    data: list[Any]


## Leaf filters with custom serialization logic due to creativity in the API design


class HasDataFilter(ListFilterDataDefinition):
    filter_type: Literal["hasData"] = Field("hasData", exclude=True)
    data: list[ViewReference | ContainerReference]

    # MyPy complains about thet signature of the method here, even though its compatible with the pydantic source code.
    # And tests are passing fine.
    @model_serializer(mode="plain")  # type: ignore[type-var]
    def serialize_model(self, info: FieldSerializationInfo) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for item in self.data:
            item_dict = item.model_dump(**vars(info))
            if isinstance(item, ViewReference):
                item_dict["type"] = "view"
            elif isinstance(item, ContainerReference):
                item_dict["type"] = "container"
            output.append(item_dict)
        return output


class InstanceReferencesFilterData(ListFilterDataDefinition):
    filter_type: Literal["instanceReferences"] = Field("instanceReferences", exclude=True)
    data: list[NodeReference]

    # MyPy complains about thet signature of the method here, even though its compatible with the pydantic source code.
    # And tests are passing fine.
    @model_serializer(mode="plain")  # type: ignore[type-var]
    def serialize_model(self, info: FieldSerializationInfo) -> list[dict[str, Any]]:
        return [item.model_dump(**vars(info)) for item in self.data]


## Logical filters combining other filters


class AndFilter(ListFilterDataDefinition):
    filter_type: Literal["and"] = Field("and", exclude=True)
    data: "list[Filter]"

    # MyPy complains about thet signature of the method here, even though its compatible with the pydantic source code.
    # And tests are passing fine.
    @model_serializer(mode="plain")  # type: ignore[type-var]
    def serialize_model(self, info: FieldSerializationInfo) -> list[dict[str, Any]]:
        return [FilterAdapter.dump_python(item, **vars(info)) for item in self.data]


class OrFilter(ListFilterDataDefinition):
    filter_type: Literal["or"] = Field("or", exclude=True)
    data: "list[Filter]"

    # MyPy complains about thet signature of the method here, even though its compatible with the pydantic source code.
    # And tests are passing fine.
    @model_serializer(mode="plain")  # type: ignore[type-var]
    def serialize_model(self, info: FieldSerializationInfo) -> list[dict[str, Any]]:
        return [FilterAdapter.dump_python(item, **vars(info)) for item in self.data]


class NotFilter(FilterDataDefinition):
    filter_type: Literal["not"] = Field("not", exclude=True)
    data: "Filter"

    # MyPy complains about thet signature of the method here, even though its compatible with the pydantic source code.
    # And tests are passing fine.
    @model_serializer(mode="plain")  # type: ignore[type-var]
    def serialize_model(self, info: FieldSerializationInfo) -> dict[str, Any]:
        return FilterAdapter.dump_python(self.data, **vars(info))


FilterData = Annotated[
    EqualsFilterData
    | PrefixFilterData
    | InFilterData
    | RangeFilterData
    | ExistsFilterData
    | ContainsAnyFilterData
    | ContainsAllFilterData
    | MatchAllFilterData
    | NestedFilterData
    | OverlapsFilterData
    | HasDataFilter
    | InstanceReferencesFilterData
    | AndFilter
    | OrFilter
    | NotFilter,
    Field(discriminator="filter_type"),
]


FilterTypes: TypeAlias = Literal[
    "equals",
    "prefix",
    "in",
    "range",
    "exists",
    "containsAny",
    "containsAll",
    "matchAll",
    "nested",
    "overlaps",
    "hasData",
    "instanceReferences",
    "and",
    "or",
    "not",
]

LegacyFilterTypes: TypeAlias = Literal["invalid"]

AVAILABLE_FILTERS: frozenset[str] = frozenset(get_args(FilterTypes))
LEGACY_FILTERS: frozenset[str] = frozenset(get_args(LegacyFilterTypes))


def _move_filter_key(value: Any) -> Any:
    """The DMS API filters have an unusual structure.

    It has the filter type as the key of the outer dict, and then the actual filter data as the value, e.g.,
    {
        "equals": {
            "property": [...],
            "value": ...
        }
    }
    We could have modeled it that way with Pydantic, and had an union of pydantic models of all possible filter types.
    However, validating union types in Pydantic without a discriminator leads to poor error messages. If the filter
    data does not comply with any of the union types, Pydantic will give one error message per union type. For exampl,
    if the user writes
    {
        "equals": {
            "property": "my_property"  # Should be a list,
            "value": 'my_value'
            }
    }
    Pydantic will give 15 error messages, one for each filter type in the union, saying that the data does not
    comply with that filter type. This is not very user-friendly.

    Instead, we introduce an internal field "filter_type" inside the filter data models, and use that as a
    discriminator. This will enable the validation to be two steps. First, we validate the outer key and
    that it is a known filter type. Then, we move that key inside the filter data as the "filter_type" field, and
    validate the filter data against the correct model based on that discriminator.


    This function transforms the data from the outer-key format to the inner-key format. For example, it transforms
    the equals filter form above into

    {
        "equals": {
            "property": [...],
            "value": ...,
            "filterType": "equals"
        }
    }
    """
    # legacy filter which we want to ignore
    if _is_legacy_filter(value):
        return None
    if not isinstance(value, dict):
        return value
    if len(value) != 1:
        raise ValueError("Filter data must have exactly one key.")
    if "filterType" in value:
        # Already in the correct format
        return value
    key, data = next(iter(value.items()))
    # Check if inner data already has filterType (already processed by a previous recursive call)
    if isinstance(data, dict) and "filterType" in data:
        return value
    if key not in AVAILABLE_FILTERS:
        raise ValueError(
            f"Unknown filter type: {key!r}. Available filter types: {humanize_collection(AVAILABLE_FILTERS)}."
        )
    if isinstance(data, dict) and key == "not":
        # Not is a recursive filter, so we need to move the filter key inside its data as well
        output = _move_filter_key(data.copy())
        return {key: {"filterType": key, "data": output}}
    elif isinstance(data, dict):
        output = data.copy()
        output["filterType"] = key
        return {key: output}
    elif isinstance(data, list) and key in {"and", "or"}:
        # And and Or are recursive filters, so we need to move the filter key inside each of their data items as well
        return {key: {"filterType": key, "data": [_move_filter_key(item) for item in data]}}
    elif isinstance(data, list):
        # Leaf list filters, hasData and instanceReferences
        return {key: {"filterType": key, "data": data}}
    else:
        # Let the regular validation handle it (possible not an issue)
        return value


def _is_legacy_filter(filter_obj: Any) -> bool:
    """Check if filter is a legacy filter no longer supported by DMS API"""

    def traverse(obj: Any) -> bool:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in LEGACY_FILTERS:
                    return True
                if traverse(value):
                    return True
        elif isinstance(obj, list):
            for item in obj:
                if traverse(item):
                    return True
        return False

    return traverse(filter_obj)


Filter = Annotated[dict[FilterTypes, FilterData] | None, BeforeValidator(_move_filter_key)]

FilterAdapter: TypeAdapter[Filter] = TypeAdapter(Filter)
