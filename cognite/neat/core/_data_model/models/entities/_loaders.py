from typing import Literal

from cognite.neat.core._data_model.models.data_types import DataType
from cognite.neat.core._issues.errors import NeatTypeError

from ._multi_value import MultiValueTypeInfo
from ._single_value import (
    ConceptEntity,
    EdgeEntity,
    PhysicalUnknownEntity,
    ReverseConnectionEntity,
    Unknown,
    UnknownEntity,
    ViewEntity,
)


def load_value_type(
    raw: str | MultiValueTypeInfo | DataType | ConceptEntity | UnknownEntity,
    default_prefix: str,
) -> MultiValueTypeInfo | DataType | ConceptEntity | UnknownEntity:
    if isinstance(raw, MultiValueTypeInfo | DataType | ConceptEntity | UnknownEntity):
        return raw
    elif isinstance(raw, str):
        # property holding xsd data type
        # check if it is multi value type
        if "," in raw:
            value_type = MultiValueTypeInfo.load(raw)
            value_type.set_default_prefix(default_prefix)
            return value_type
        elif DataType.is_data_type(raw):
            return DataType.load(raw)

        # unknown value type
        elif raw == str(Unknown):
            return UnknownEntity()

        # property holding link to class
        else:
            return ConceptEntity.load(raw, prefix=default_prefix)
    else:
        raise NeatTypeError(f"Invalid value type: {type(raw)}")


def load_dms_value_type(
    raw: str | DataType | ViewEntity | PhysicalUnknownEntity,
    default_space: str,
    default_version: str,
) -> DataType | ViewEntity | PhysicalUnknownEntity:
    if isinstance(raw, DataType | ViewEntity | PhysicalUnknownEntity):
        return raw
    elif isinstance(raw, str):
        if DataType.is_data_type(raw):
            return DataType.load(raw)
        elif raw == str(Unknown):
            return PhysicalUnknownEntity()
        else:
            return ViewEntity.load(raw, space=default_space, version=default_version)
    raise NeatTypeError(f"Invalid value type: {type(raw)}")


def load_connection(
    raw: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | str | None,
    default_space: str,
    default_version: str,
) -> Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None:
    if isinstance(raw, str) and raw.lower() == "direct":
        return "direct"  # type: ignore[return-value]
    elif isinstance(raw, EdgeEntity | ReverseConnectionEntity) or raw is None:
        return raw  # type: ignore[return-value]
    elif isinstance(raw, str) and raw.startswith("edge"):
        return EdgeEntity.load(raw, space=default_space, version=default_version)  # type: ignore[return-value]
    elif isinstance(raw, str) and raw.startswith("reverse"):
        return ReverseConnectionEntity.load(raw)  # type: ignore[return-value]
    raise NeatTypeError(f"Invalid connection: {type(raw)}")
