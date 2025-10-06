from abc import ABC
from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter, field_validator

from ._base import BaseModelObject


class IndexDefinition(BaseModelObject, ABC):
    index_type: str
    properties: list[str] = Field(description="List of properties to define the index across.")


class BtreeIndex(IndexDefinition):
    index_type: Literal["btree"] = "btree"
    by_space: bool | None = Field(default=None, description="Whether to make the index space-specific.")
    cursorable: bool | None = Field(
        default=None, description="Whether the index can be used for cursor-based pagination."
    )

    @field_validator("cursorable", mode="before")
    def string_to_bool(cls, value: Any) -> Any:
        if isinstance(value, str):
            if value.lower() in {"true", "yes", "1"}:
                return True
            elif value.lower() in {"false", "no", "0"}:
                return False
        return value


class InvertedIndex(IndexDefinition):
    index_type: Literal["inverted"] = "inverted"


Index = Annotated[BtreeIndex | InvertedIndex, Field(discriminator="index_type")]

IndexAdapter: TypeAdapter[Index] = TypeAdapter(Index)
