from abc import ABC
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BeforeValidator, Field, JsonValue, TypeAdapter, model_serializer, model_validator
from pydantic_core.core_schema import FieldSerializationInfo

from cognite.neat._utils.useful_types import BaseModelObject

from ._references import ContainerReference, NodeReference, ViewReference


class Parameter(BaseModelObject):
    parameter: str


class FilterDataDefinition(BaseModelObject, ABC):
    """Base class for filter data models."""

    filter_type: str = Field(..., exclude=True)


class PropertyReference(FilterDataDefinition, ABC):
    """Represents the property path in filters."""

    property: list[str] = Field(..., min_length=2, max_length=3)


class EqualsData(PropertyReference):
    filter_type: Literal["equals"] = Field("equals", exclude=True)
    value: JsonValue | PropertyReference


class InData(PropertyReference):
    filter_type: Literal["in"] = "in"
    values: list[JsonValue] | PropertyReference


class RangeData(PropertyReference):
    filter_type: Literal["range"] = "range"
    gt: str | int | float | PropertyReference | None = None
    gte: str | int | float | PropertyReference | None = None
    lt: str | int | float | PropertyReference | None = None
    lte: str | int | float | PropertyReference | None = None


class PrefixData(PropertyReference):
    filter_type: Literal["prefix"] = "prefix"
    value: str | Parameter


class ExistsData(PropertyReference):
    filter_type: Literal["exists"] = "exists"


class ContainsAnyData(PropertyReference):
    filter_type: Literal["containsAny"] = "containsAny"
    values: list[JsonValue] | PropertyReference


class ContainsAllData(PropertyReference):
    filter_type: Literal["containsAll"] = "containsAll"
    values: list[JsonValue] | PropertyReference


class MatchAllData(FilterDataDefinition):
    filter_type: Literal["matchAll"] = "matchAll"


class NestedData(PropertyReference):
    filter_type: Literal["nested"] = "nested"
    scope: list[str] = Field(..., min_length=1, max_length=3)
    filter: "Filter"


class OverlapsData(PropertyReference):
    filter_type: Literal["overlaps"] = "overlaps"
    start_property: list[str] = Field(..., min_length=1, max_length=3)
    end_property: list[str] = Field(..., min_length=1, max_length=3)
    gt: str | int | float | PropertyReference | None = None
    gte: str | int | float | PropertyReference | None = None
    lt: str | int | float | PropertyReference | None = None
    lte: str | int | float | PropertyReference | None = None


class AndFilter(BaseModelObject):
    and_: "list[Filter]" = Field(alias="and")


class OrFilter(BaseModelObject):
    or_: "list[Filter]" = Field(alias="or")


class NotFilter(BaseModelObject):
    not_: "Filter" = Field(alias="not")


class EqualsFilter(BaseModelObject):
    equals: EqualsData


class PrefixFilter(BaseModelObject):
    prefix: PrefixData


class InFilter(BaseModelObject):
    in_: InData = Field(alias="in")


class RangeFilter(BaseModelObject):
    range: RangeData


class ExistsFilter(BaseModelObject):
    exists: ExistsData


class ContainsAnyFilter(BaseModelObject):
    containsAny: ContainsAnyData


class ContainsAllFilter(BaseModelObject):
    containsAll: ContainsAllData


class MatchAllFilter(BaseModelObject):
    matchAll: MatchAllData


class NestedFilter(BaseModelObject):
    nested: NestedData


class OverlapsFilter(BaseModelObject):
    overlaps: OverlapsData


class HasDataFilter(BaseModelObject):
    references: list[ViewReference | ContainerReference]

    @model_validator(mode="before")
    @classmethod
    def validate_model(cls, data: Any) -> dict[str, Any]:
        if isinstance(data, list):
            return {"references": data}
        elif isinstance(data, dict) and "hasData" in data:
            return {"references": data["hasData"]}
        return data

    # MyPy says that the model_serializer decorator does not take
    # 'Callable[[HasDataFilter, FieldSerializationInfo]], dict[str, Any]]' type: ignore[ERA001]
    # However, checking the pydantic source code, it is clear that it does
    # (Callable[[Any, FieldSerializationInfo]], Any]) is the expected type.)
    # In addition, the tests confirm that this works as intended.
    @model_serializer(mode="plain")  # type: ignore[type-var]
    def serialize_model(self, info: FieldSerializationInfo) -> dict[str, Any]:
        references: list[dict[str, Any]] = []
        for ref in self.references:
            dumped = ref.model_dump(**vars(info))
            if isinstance(ref, ViewReference):
                dumped["type"] = "view"
            elif isinstance(ref, ContainerReference):
                dumped["type"] = "container"
            references.append(dumped)
        return {"hasData": references}


class InstanceReferencesFilter(BaseModelObject):
    references: list[NodeReference]

    @model_validator(mode="before")
    def validate_model(cls, data: Any) -> dict[str, Any]:
        if isinstance(data, list):
            return {"references": data}
        elif isinstance(data, dict) and "instanceReferences" in data:
            return {"references": data["instanceReferences"]}
        return data

    # MyPy says that the model_serializer decorator does not take
    # 'Callable[[InstanceReferencesFilter,FieldSerializationInfo]], dict[str, Any]]' type: ignore[ERA001]
    # However, checking the pydantic source code, it is clear that it does
    # (Callable[[Any, FieldSerializationInfo]], Any]) is the expected type.)
    # In addition, the tests confirm that this works as intended.
    @model_serializer(mode="plain")  # type: ignore[type-var]
    def serialize_model(self, info: FieldSerializationInfo) -> dict[str, Any]:
        return {"instanceReferences": [ref.model_dump(**vars(info)) for ref in self.references]}


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
    | OverlapsData,
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
    "and",
    "or",
    "not",
    "hasData",
    "instanceReferences",
]


def _move_filter_key(data: dict[str, Any]) -> dict[str, Any]:
    if len(data) != 1:
        raise ValueError("Filter data must have exactly one key.")
    key, data = next(iter(data.items()))
    output = data.copy()
    output["filter_type"] = key
    return {key: output}


Filter = Annotated[dict[FilterTypes, FilterData], BeforeValidator(_move_filter_key)]

FilterAdapter: TypeAdapter[Filter] = TypeAdapter(Filter)
