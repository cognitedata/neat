from typing import Literal

from cognite.neat._issues.errors import NeatTypeError
from cognite.neat._rules.models.data_types import DataType

from ._multi_value import MultiValueTypeInfo
from ._single_value import (
    ClassEntity,
    DMSUnknownEntity,
    EdgeEntity,
    ReverseConnectionEntity,
    Unknown,
    UnknownEntity,
    ViewEntity,
)


def load_value_type(
    raw: str | MultiValueTypeInfo | DataType | ClassEntity | UnknownEntity, default_prefix: str
) -> MultiValueTypeInfo | DataType | ClassEntity | UnknownEntity:
    if isinstance(raw, MultiValueTypeInfo | DataType | ClassEntity | UnknownEntity):
        return raw
    elif isinstance(raw, str):
        # property holding xsd data type
        # check if it is multi value type
        if "|" in raw:
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
            return ClassEntity.load(raw, prefix=default_prefix)
    else:
        raise NeatTypeError(f"Invalid value type: {type(raw)}")


def load_dms_value_type(
    raw: str | DataType | ViewEntity | DMSUnknownEntity,
    default_space: str,
    default_version: str,
) -> DataType | ViewEntity | DMSUnknownEntity:
    if isinstance(raw, DataType | ViewEntity | DMSUnknownEntity):
        return raw
    elif isinstance(raw, str):
        if DataType.is_data_type(raw):
            return DataType.load(raw)
        elif raw == str(Unknown):
            return DMSUnknownEntity()
        else:
            return ViewEntity.load(raw, space=default_space, version=default_version)
    raise NeatTypeError(f"Invalid value type: {type(raw)}")


def load_connection(
    raw: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | str | None,
    default_space: str,
    default_version: str,
) -> Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None:
    if (
        isinstance(raw, EdgeEntity | ReverseConnectionEntity)
        or raw is None
        or (isinstance(raw, str) and raw == "direct")
    ):
        return raw  # type: ignore[return-value]
    elif isinstance(raw, str) and raw.startswith("edge"):
        return EdgeEntity.load(raw, space=default_space, version=default_version)  # type: ignore[return-value]
    elif isinstance(raw, str) and raw.startswith("reverse"):
        return ReverseConnectionEntity.load(raw)  # type: ignore[return-value]
    raise NeatTypeError(f"Invalid connection: {type(raw)}")
