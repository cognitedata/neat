from abc import ABC
from typing import Annotated, Literal

from pydantic import Field

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


class InvertedIndex(IndexDefinition):
    index_type: Literal["inverted"] = "inverted"


Index = Annotated[BtreeIndex | InvertedIndex, Field(discriminator="index_type")]
