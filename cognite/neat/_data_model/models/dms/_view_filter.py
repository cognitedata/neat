from abc import ABC
from typing import Annotated, Any, Literal

from pydantic import Field, JsonValue, TypeAdapter, model_serializer, model_validator

from cognite.neat._utils.useful_types import BaseModelObject

from ._references import ContainerReference, NodeReference, ViewReference


class PropertyReference(BaseModelObject, ABC):
    """Represents the property path in filters."""

    property: list[str] = Field(..., min_length=2, max_length=3)


class Parameter(BaseModelObject):
    parameter: str


class EqualsFilter(PropertyReference):
    value: JsonValue | PropertyReference


class InFilter(PropertyReference):
    values: list[JsonValue] | PropertyReference


class RangeFilter(PropertyReference):
    gt: str | int | float | PropertyReference | None = None
    gte: str | int | float | PropertyReference | None = None
    lt: str | int | float | PropertyReference | None = None
    lte: str | int | float | PropertyReference | None = None


class PrefixFilter(PropertyReference):
    value: str | Parameter


class ExistsFilter(PropertyReference): ...


class ContainsAnyFilter(PropertyReference):
    values: list[JsonValue] | PropertyReference


class ContainsAllFilter(PropertyReference):
    values: list[JsonValue] | PropertyReference


class MatchAllFilter(BaseModelObject):
    pass


class NestedFilter(PropertyReference):
    scope: list[str] = Field(..., min_length=1, max_length=3)
    filter: "Filter"


class OverlapsFilter(PropertyReference):
    start_property: list[str] = Field(..., min_length=1, max_length=3)
    end_property: list[str] = Field(..., min_length=1, max_length=3)
    gt: str | int | float | PropertyReference | None = None
    gte: str | int | float | PropertyReference | None = None
    lt: str | int | float | PropertyReference | None = None
    lte: str | int | float | PropertyReference | None = None


class HasDataFilter(BaseModelObject):
    references: list[ViewReference | ContainerReference]

    @model_serializer
    def serialize_model(self) -> list[dict[str, Any]]:
        # Custom serialization logic
        return [ref.model_dump() for ref in self.references]

    @model_validator(mode="before")
    def validate_model(cls, data: Any) -> dict[str, Any]:
        if isinstance(data, list):
            return {"references": data}
        return data


# Forward reference for recursive definition
Filter = Annotated[
    dict[Literal["and"], list["Filter"]]
    | dict[Literal["or"], list["Filter"]]
    | dict[Literal["not"], "Filter"]
    | dict[Literal["equals"], EqualsFilter]
    | dict[Literal["prefix"], PrefixFilter]
    | dict[Literal["in"], InFilter]
    | dict[Literal["range"], RangeFilter]
    | dict[Literal["exists"], ExistsFilter]
    | dict[Literal["containsAny"], ContainsAnyFilter]
    | dict[Literal["containsAll"], ContainsAllFilter]
    | dict[Literal["matchAll"], MatchAllFilter]
    | dict[Literal["nested"], NestedFilter]
    | dict[Literal["overlaps"], OverlapsFilter]
    | dict[Literal["hasData"], HasDataFilter]
    | dict[Literal["instanceReferences"], list[NodeReference]],
    Field(discriminator=None),
]

FilterAdapter: TypeAdapter[Filter] = TypeAdapter(Filter)
