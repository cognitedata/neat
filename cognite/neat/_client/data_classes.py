from typing import Generic, TypeVar

from pydantic import BaseModel, Field, JsonValue

T = TypeVar("T", bound=BaseModel)


class PagedResponse(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = Field(None, alias="nextCursor")


class ErrorResponse(BaseModel):
    code: int
    message: str
    missing: list[JsonValue] | None = None
    duplicated: list[JsonValue] | None = None
