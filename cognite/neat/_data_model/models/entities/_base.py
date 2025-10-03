from functools import total_ordering
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_serializer

from ._constants import (
    PREFIX_PATTERN,
    SUFFIX_PATTERN,
    VERSION_PATTERN,
    Undefined,
    Unknown,
    _UndefinedType,
    _UnknownType,
)


@total_ordering
class Entity(BaseModel, extra="ignore", populate_by_name=True):
    """Entity is a concept, class, property, datatype in semantics sense."""

    prefix: str | _UndefinedType = Field(default=Undefined, pattern=PREFIX_PATTERN, min_length=1, max_length=43)
    suffix: str = Field(min_length=1, max_length=255, pattern=SUFFIX_PATTERN)

    @model_serializer(when_used="unless-none", return_type=str)
    def as_str(self) -> str:
        return str(self)

    @field_validator("*", mode="before")
    def strip_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        elif isinstance(value, list):
            return [entry.strip() if isinstance(entry, str) else entry for entry in value]
        return value

    def as_tuple(self) -> tuple[str, ...]:
        # We haver overwritten the serialization to str, so we need to do it manually
        extra: tuple[str, ...] = tuple(
            [
                str(v or "")
                for field_name in self.model_fields.keys()
                if (v := getattr(self, field_name)) and field_name not in {"prefix", "suffix"}
            ]
        )
        if isinstance(self.prefix, _UndefinedType):
            return str(self.suffix), *extra
        else:
            return self.prefix, str(self.suffix), *extra

    def __lt__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return self.as_tuple() < other.as_tuple()  # type: ignore[attr-defined]

    def __eq__(self, other: object) -> bool:
        # We need to be explicit that we are not allowing comparison between different types
        if type(other) is not type(self):
            # requires explicit raising as NotImplemented would lead to running comparison
            raise TypeError(f"'==' not supported between instances of {type(self).__name__} and {type(other).__name__}")
        return self.as_tuple() == other.as_tuple()  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return hash(f"{type(self).__name__}({self})")

    def __str__(self) -> str:
        # there are three cases for string representation:
        # 1. only suffix is present -> return str(suffix)
        # 2. prefix and suffix are present -> return "prefix:suffix"
        # 3. prefix, suffix and other fields are present -> return "prefix:suffix(field1=value1,field2=value2)"

        model_dump = {k: v for k in self.model_fields if (v := getattr(self, k)) is not None}

        base_str = f"{self.prefix}:{self.suffix}" if not isinstance(self.prefix, _UndefinedType) else str(self.suffix)

        extra_fields = {
            (self.model_fields[k].alias or k): v for k, v in model_dump.items() if k not in {"prefix", "suffix"}
        }
        if extra_fields:
            extra_str = ",".join([f"{k}={v}" for k, v in extra_fields.items()])
            return f"{base_str}({extra_str})"
        else:
            return base_str

    def __repr__(self) -> str:
        # We have overwritten the serialization to str, so we need to do it manually
        model_dump = {k: v for k in self.model_fields if (v := getattr(self, k)) is not None}
        args = ",".join([f"{k}={v!r}" for k, v in model_dump.items()])
        return f"{type(self).__name__}({args})"


class ConceptEntity(Entity):
    version: str | None = Field(default=None, pattern=VERSION_PATTERN, max_length=43)


class UnknownEntity(ConceptEntity):
    prefix: _UndefinedType = Undefined
    suffix: _UnknownType = Unknown  # type: ignore[assignment]

    @property
    def id(self) -> str:
        return str(Unknown)
