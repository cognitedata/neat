from typing import Literal, overload

from cognite.neat.v0.core._data_model.models.data_types import DataType
from cognite.neat.v0.core._issues.errors import NeatTypeError

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


@overload
def load_value_type(
    raw: str | MultiValueTypeInfo | DataType | ConceptEntity | UnknownEntity,
    default_prefix: str,
    return_on_failure: Literal[False] = False,
) -> MultiValueTypeInfo | DataType | ConceptEntity | UnknownEntity: ...


@overload
def load_value_type(
    raw: str | MultiValueTypeInfo | DataType | ConceptEntity | UnknownEntity,
    default_prefix: str,
    return_on_failure: Literal[True],
) -> MultiValueTypeInfo | DataType | ConceptEntity | UnknownEntity | None | str: ...


def load_value_type(
    raw: str | MultiValueTypeInfo | DataType | ConceptEntity | UnknownEntity,
    default_prefix: str,
    return_on_failure: Literal[True, False] = False,
) -> MultiValueTypeInfo | DataType | ConceptEntity | UnknownEntity | None | str:
    """
    Loads a value type from a raw string or entity.

    Args:
        raw: The raw value to load.
        default_prefix: The default prefix to use if not specified in the raw value.
        return_on_failure: If True, returns the raw value on parsing failure instead of raising an error.

    Returns:
        The loaded value type entity, or the raw value if loading fails and `return_on_failure` is True.
    """
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
            return ConceptEntity.load(raw, prefix=default_prefix, return_on_failure=return_on_failure)
    else:
        raise NeatTypeError(f"Invalid value type: {type(raw)}")


@overload
def load_dms_value_type(
    raw: str | DataType | ViewEntity | PhysicalUnknownEntity,
    default_space: str,
    default_version: str,
    return_on_failure: Literal[False],
) -> DataType | ViewEntity | PhysicalUnknownEntity: ...


@overload
def load_dms_value_type(
    raw: str | DataType | ViewEntity | PhysicalUnknownEntity,
    default_space: str,
    default_version: str,
    return_on_failure: Literal[True],
) -> DataType | ViewEntity | PhysicalUnknownEntity | str: ...


def load_dms_value_type(
    raw: str | DataType | ViewEntity | PhysicalUnknownEntity,
    default_space: str,
    default_version: str,
    return_on_failure: Literal[True, False] = False,
) -> DataType | ViewEntity | PhysicalUnknownEntity | str:
    """
    Loads a value type from a raw string or entity in the context of a data modeling service

    Args:
        raw: The raw value to load.
        default_space: The default space to use if not specified in the raw value.
        default_version: The default version to use if not specified in the raw value.
        return_on_failure: If True, returns the raw value on parsing failure instead of raising an error.

    Returns:
        The loaded value type entity, or the raw value if loading fails and `return_on_failure` is True.
    """
    if isinstance(raw, DataType | ViewEntity | PhysicalUnknownEntity):
        return raw
    elif isinstance(raw, str):
        if DataType.is_data_type(raw):
            return DataType.load(raw)
        elif raw == str(Unknown):
            return PhysicalUnknownEntity()
        else:
            return ViewEntity.load(
                raw, space=default_space, version=default_version, return_on_failure=return_on_failure
            )
    raise NeatTypeError(f"Invalid value type: {type(raw)}")


@overload
def load_connection(
    raw: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | str | None,
    default_space: str,
    default_version: str,
    return_on_failure: Literal[False] = False,
) -> Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None: ...


@overload
def load_connection(
    raw: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | str | None,
    default_space: str,
    default_version: str,
    return_on_failure: Literal[True],
) -> Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None | str: ...


def load_connection(
    raw: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | str | None,
    default_space: str,
    default_version: str,
    return_on_failure: Literal[True, False] = False,
) -> Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None | str:
    if isinstance(raw, str) and raw.lower() == "direct":
        return "direct"  # type: ignore[return-value]
    elif isinstance(raw, EdgeEntity | ReverseConnectionEntity) or raw is None:
        return raw  # type: ignore[return-value]
    elif isinstance(raw, str) and raw.startswith("edge"):
        return EdgeEntity.load(raw, space=default_space, version=default_version, return_on_failure=return_on_failure)  # type: ignore[return-value]
    elif isinstance(raw, str) and raw.startswith("reverse"):
        return ReverseConnectionEntity.load(raw, return_on_failure=return_on_failure)  # type: ignore[return-value]
    raise NeatTypeError(f"Invalid connection: {type(raw)}")
