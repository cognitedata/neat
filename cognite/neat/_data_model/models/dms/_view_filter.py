from abc import ABC
from typing import Any

from pydantic import Field, JsonValue, TypeAdapter, model_serializer, model_validator
from pydantic_core.core_schema import FieldSerializationInfo

from cognite.neat._utils.useful_types import BaseModelObject

from ._references import ContainerReference, NodeReference, ViewReference


class PropertyReference(BaseModelObject, ABC):
    """Represents the property path in filters."""

    property: list[str] = Field(..., min_length=2, max_length=3)


class Parameter(BaseModelObject):
    parameter: str


class EqualsData(PropertyReference):
    value: JsonValue | PropertyReference


class InData(PropertyReference):
    values: list[JsonValue] | PropertyReference


class RangeData(PropertyReference):
    gt: str | int | float | PropertyReference | None = None
    gte: str | int | float | PropertyReference | None = None
    lt: str | int | float | PropertyReference | None = None
    lte: str | int | float | PropertyReference | None = None


class PrefixData(PropertyReference):
    value: str | Parameter


class ExistsData(PropertyReference): ...


class ContainsAnyData(PropertyReference):
    values: list[JsonValue] | PropertyReference


class ContainsAllData(PropertyReference):
    values: list[JsonValue] | PropertyReference


class MatchAllData(BaseModelObject):
    pass


class NestedData(PropertyReference):
    scope: list[str] = Field(..., min_length=1, max_length=3)
    filter: "Filter"


class OverlapsData(PropertyReference):
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
    def validate_model(cls, data: Any) -> dict[str, Any]:
        if isinstance(data, list):
            return {"references": data}
        elif isinstance(data, dict) and "hasData" in data:
            return {"references": data["hasData"]}
        return data

    @model_serializer(mode="plain", return_type=dict[str, Any])
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

    @model_serializer(mode="plain", return_type=dict[str, Any])
    def serialize_model(self, info: FieldSerializationInfo) -> dict[str, Any]:
        return {"instanceReferences": [ref.model_dump(**vars(info)) for ref in self.references]}


Filter = (
    AndFilter
    | OrFilter
    | NotFilter
    | EqualsFilter
    | PrefixFilter
    | InFilter
    | RangeFilter
    | ExistsFilter
    | ContainsAnyFilter
    | ContainsAllFilter
    | MatchAllFilter
    | NestedFilter
    | OverlapsFilter
    | HasDataFilter
    | InstanceReferencesFilter
)

FilterAdapter: TypeAdapter[Filter] = TypeAdapter(Filter)
