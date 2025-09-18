from functools import total_ordering
from typing import Any, ClassVar, TypeVar

from cognite.client.data_classes.data_modeling.data_types import UnitReference
from pydantic import (
    BaseModel,
    field_validator,
    model_serializer,
)

from cognite.neat.data_model._constants import (
    EntityTypes,
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

    type_: ClassVar[EntityTypes] = EntityTypes.undefined
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

    def dump(self, **defaults: Any) -> str:
        return self._as_str(**defaults)

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
        return self.id

    def __repr__(self) -> str:
        # We have overwritten the serialization to str, so we need to do it manually
        model_dump = ((k, v) for k in self.model_fields if (v := getattr(self, k)) is not None)
        args = ",".join([f"{k}={v}" for k, v in model_dump])
        return f"{self.type_.value}({args})"

    @property
    def id(self) -> str:
        return self._as_str()

    def _as_str(self, **defaults: Any) -> str:
        # We have overwritten the serialization to str, so we need to do it manually
        model_dump = {
            field.alias or field_name: v.dump(**defaults) if isinstance(v, ConceptualEntity) else v
            for field_name, field in self.model_fields.items()
            if (v := getattr(self, field_name)) is not None and field_name not in {"prefix", "suffix"}
        }
        # We only remove the default values if all the fields are default
        # For example, if we dump `cdf_cdm:CogniteAsset(version=v1)` and the default is `version=v1`,
        # we should not remove it unless the space is `cdf_cdm`
        to_delete: list[str] = []
        is_removing_defaults = True
        if isinstance(defaults, dict):
            for key, value in defaults.items():
                if key not in model_dump:
                    continue
                if model_dump[key] == value:
                    to_delete.append(key)
                else:
                    # Not all fields are default. We should not remove any of them.
                    is_removing_defaults = False
                    break
        if isinstance(defaults, dict) and self.prefix == defaults.get("prefix") and is_removing_defaults:
            base_id = str(self.suffix)
        elif self.prefix == Undefined:
            base_id = str(self.suffix)
        else:
            is_removing_defaults = False
            base_id = f"{self.prefix}:{self.suffix!s}"
        if is_removing_defaults:
            for key in to_delete:
                del model_dump[key]
        # Sorting to ensure deterministic order
        args = ",".join(f"{k}={v}" for k, v in sorted(model_dump.items(), key=lambda x: x[0]))
        if args:
            return f"{base_id}({args})"
        else:
            return base_id


T_Entity = TypeVar("T_Entity", bound=ConceptualEntity)


class ConceptEntity(ConceptualEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.concept
    version: str | None = None


class UnknownEntity(ConceptEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.undefined
    prefix: _UndefinedType = Undefined
    suffix: _UnknownType = Unknown  # type: ignore[assignment]

    @property
    def id(self) -> str:
        return str(Unknown)


class UnitEntity(ConceptualEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.unit
    prefix: str
    suffix: str

    def as_reference(self) -> UnitReference:
        return UnitReference(external_id=f"{self.prefix}:{self.suffix}")
