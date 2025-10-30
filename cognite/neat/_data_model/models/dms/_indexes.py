from abc import ABC
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from cognite.neat._utils.useful_types import BaseModelObject

from ._types import Bool


class IndexDefinition(BaseModelObject, ABC):
    index_type: str
    properties: list[str] = Field(description="List of properties to define the index across.")


class BtreeIndex(IndexDefinition):
    index_type: Literal["btree"] = "btree"
    by_space: Bool | None = Field(default=None, description="Whether to make the index space-specific.")
    cursorable: Bool | None = Field(
        default=None, description="Whether the index can be used for cursor-based pagination."
    )


class InvertedIndex(IndexDefinition):
    index_type: Literal["inverted"] = "inverted"


Index = Annotated[BtreeIndex | InvertedIndex, Field(discriminator="index_type")]

IndexAdapter: TypeAdapter[Index] = TypeAdapter(Index)
