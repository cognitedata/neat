from functools import total_ordering
from typing import Any

from cognite.client.data_classes.data_modeling.data_types import UnitReference
from pydantic import (
    BaseModel,
    field_validator,
    model_serializer,
)

from ._constants import (
    Undefined,
    Unknown,
    _UndefinedType,
    _UnknownType,
)


@total_ordering
class ConceptualEntity(BaseModel, extra="ignore"):
    """Conceptual Entity is a concept, class or property in semantics sense."""

    prefix: str | _UndefinedType = Undefined
    suffix: str

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
        if not isinstance(other, ConceptualEntity):
            return NotImplemented
        return self.as_tuple() < other.as_tuple()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConceptualEntity):
            return NotImplemented
        return self.as_tuple() == other.as_tuple()

    def __hash__(self) -> int:
        return hash(str(self))

    def __str__(self) -> str:
        # We have overwritten the serialization to str, so we need to do it manually
        model_dump = {k: v for k in self.model_fields if (v := getattr(self, k)) is not None}

        # there are three cases to process model_dump:
        # 1. only suffix is present -> return str(suffix)
        # 2. prefix and suffix are present -> return "prefix:suffix"
        # 3. prefix, suffix and other fields are present -> return "prefix:suffix(field1=value1,field2=value2)"

        base_str = f"{self.prefix}:{self.suffix}" if not isinstance(self.prefix, _UndefinedType) else str(self.suffix)

        # Get extra fields (excluding prefix and suffix)
        extra_fields = {k: v for k, v in model_dump.items() if k not in {"prefix", "suffix"}}

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


class ConceptEntity(ConceptualEntity):
    version: str | None = None


class UnknownEntity(ConceptEntity):
    prefix: _UndefinedType = Undefined
    suffix: _UnknownType = Unknown  # type: ignore[assignment]

    @property
    def id(self) -> str:
        return str(Unknown)


class UnitEntity(ConceptualEntity):
    prefix: str
    suffix: str

    def as_reference(self) -> UnitReference:
        return UnitReference(external_id=f"{self.prefix}:{self.suffix}")
