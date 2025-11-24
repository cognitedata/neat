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

    filter_type: str = Field(..., exclude=True)


class PropertyReference(FilterDataDefinition, ABC):
    """Represents the property path in filters."""

    property: list[str] = Field(..., min_length=2, max_length=3)


## Leaf filters that follows the standard pattern


class EqualsData(PropertyReference):
    filter_type: Literal["equals"] = Field("equals", exclude=True)
    value: JsonValue | PropertyReference


class InData(PropertyReference):
    filter_type: Literal["in"] = Field("in", exclude=True)
    values: list[JsonValue] | PropertyReference


class RangeData(PropertyReference):
    filter_type: Literal["range"] = Field("range", exclude=True)
    gt: str | int | float | PropertyReference | None = None
    gte: str | int | float | PropertyReference | None = None
    lt: str | int | float | PropertyReference | None = None
    lte: str | int | float | PropertyReference | None = None


class PrefixData(PropertyReference):
    filter_type: Literal["prefix"] = Field("prefix", exclude=True)
    value: str | Parameter


class ExistsData(PropertyReference):
    filter_type: Literal["exists"] = Field("exists", exclude=True)


class ContainsAnyData(PropertyReference):
    filter_type: Literal["containsAny"] = Field("containsAny", exclude=True)
    values: list[JsonValue] | PropertyReference


class ContainsAllData(PropertyReference):
    filter_type: Literal["containsAll"] = Field("containsAll", exclude=True)
    values: list[JsonValue] | PropertyReference


class MatchAllData(FilterDataDefinition):
    filter_type: Literal["matchAll"] = Field("matchAll", exclude=True)


class NestedData(PropertyReference):
    filter_type: Literal["nested"] = Field("nested", exclude=True)
    scope: list[str] = Field(..., min_length=1, max_length=3)
    filter: "Filter"


class OverlapsData(PropertyReference):
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


class InstanceReferencesData(ListFilterDataDefinition):
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
    EqualsData
    | PrefixData
    | InData
    | RangeData
    | ExistsData
    | ContainsAnyData
    | ContainsAllData
    | MatchAllData
    | NestedData
    | OverlapsData
    | HasDataFilter
    | InstanceReferencesData
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

AVAILABLE_FILTERS: frozenset[str] = frozenset(get_args(FilterTypes))


def _move_filter_key(data: dict[str, Any]) -> dict[str, Any]:
    """The issus is that the API have the filter type on the outside, e.g.,
    {
        "equals": {
            "property": [...],
            "value": ...
        }
    }
    but our models have the filter type on the inside, e.g.,

    {
        "property": [...],
        "value": ...,
        "filter_type": "equals"
    }
    This function moves the filter type from the outside to the inside.
    """
    if len(data) != 1:
        raise ValueError("Filter data must have exactly one key.")
    if "filterType" in data:
        # Already in the correct format
        return data
    key, data = next(iter(data.items()))
    if key not in AVAILABLE_FILTERS:
        raise ValueError(
            f"Unknown filter type: {key!r}. Available filter types: {humanize_collection(AVAILABLE_FILTERS)}."
        )
    if isinstance(data, dict) and key == "not":
        output = _move_filter_key(data.copy())
        return {key: {"filterType": key, "data": output}}
    elif isinstance(data, dict):
        output = data.copy()
        output["filterType"] = key
        return {key: output}
    elif isinstance(data, list) and key in {"and", "or"}:
        return {key: {"filterType": key, "data": [_move_filter_key(item) for item in data]}}
    elif isinstance(data, list):
        return {key: {"filterType": key, "data": data}}
    else:
        raise ValueError("Filter data must be a dict or a list.")


Filter = Annotated[dict[FilterTypes, FilterData], BeforeValidator(_move_filter_key)]

FilterAdapter: TypeAdapter[Filter] = TypeAdapter(Filter)
