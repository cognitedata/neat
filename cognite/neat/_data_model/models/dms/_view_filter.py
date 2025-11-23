from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any

from pydantic import Field, JsonValue, TypeAdapter, model_serializer, model_validator

if TYPE_CHECKING:
    pass

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
    filter: Filter


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


# We need to use a different approach - wrap each filter type in a discriminated union


class AndFilter(BaseModelObject):
    and_: list[Filter] = Field(alias="and")


class OrFilter(BaseModelObject):
    or_: list[Filter] = Field(alias="or")


class NotFilter(BaseModelObject):
    not_: Filter = Field(alias="not")


class EqualsFilterWrapper(BaseModelObject):
    equals: EqualsFilter


class PrefixFilterWrapper(BaseModelObject):
    prefix: PrefixFilter


class InFilterWrapper(BaseModelObject):
    in_: InFilter = Field(alias="in")


class RangeFilterWrapper(BaseModelObject):
    range: RangeFilter


class ExistsFilterWrapper(BaseModelObject):
    exists: ExistsFilter


class ContainsAnyFilterWrapper(BaseModelObject):
    containsAny: ContainsAnyFilter


class ContainsAllFilterWrapper(BaseModelObject):
    containsAll: ContainsAllFilter


class MatchAllFilterWrapper(BaseModelObject):
    matchAll: MatchAllFilter


class NestedFilterWrapper(BaseModelObject):
    nested: NestedFilter


class OverlapsFilterWrapper(BaseModelObject):
    overlaps: OverlapsFilter


class HasDataFilterWrapper(BaseModelObject):
    hasData: HasDataFilter


class InstanceReferencesFilterWrapper(BaseModelObject):
    instanceReferences: list[NodeReference]


# Now create the discriminated union
Filter = (
    AndFilter
    | OrFilter
    | NotFilter
    | EqualsFilterWrapper
    | PrefixFilterWrapper
    | InFilterWrapper
    | RangeFilterWrapper
    | ExistsFilterWrapper
    | ContainsAnyFilterWrapper
    | ContainsAllFilterWrapper
    | MatchAllFilterWrapper
    | NestedFilterWrapper
    | OverlapsFilterWrapper
    | HasDataFilterWrapper
    | InstanceReferencesFilterWrapper
)

FilterAdapter: TypeAdapter[Filter] = TypeAdapter(Filter)
