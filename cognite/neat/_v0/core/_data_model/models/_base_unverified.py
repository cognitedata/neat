"""Module for base classes for the unverified models.

The philosophy of the unverified data models is:

* Provide an easy way to read data model into neat. The type hints are made to be human-friendly,
  for example, Literal instead of Enum.
* The .dump() method should fill out defaults and have shortcuts. For example, if the prefix is not provided for
  a class, then the prefix from the metadata is used. For views, if the class is not provided, it is assumed to
  be the same as the view.

The base classes are to make it easy to create the unverified data models with default behavior.
They are also used for testing to ensure that unverified models correctly map to the verified models.
"""

import sys
from abc import ABC, abstractmethod
from dataclasses import Field, dataclass, fields, is_dataclass
from types import GenericAlias, UnionType
from typing import Any, Generic, TypeVar, Union, cast, get_args, get_origin, overload

import pandas as pd

from ._base_verified import BaseVerifiedDataModel, SchemaModel

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

T_BaseDataModel = TypeVar("T_BaseDataModel", bound=BaseVerifiedDataModel)
T_DataModel = TypeVar("T_DataModel", bound=SchemaModel)


@dataclass
class UnverifiedDataModel(Generic[T_BaseDataModel], ABC):
    """Input data model are raw data that is not yet validated."""

    @classmethod
    @abstractmethod
    def _get_verified_cls(cls) -> type[T_BaseDataModel]:
        raise NotImplementedError("This method should be implemented in the subclass.")

    @classmethod
    @overload
    def load(cls: "type[T_UnverifiedDataModel]", data: dict[str, Any]) -> "T_UnverifiedDataModel": ...

    @classmethod
    @overload
    def load(cls: "type[T_UnverifiedDataModel]", data: None) -> None: ...

    @classmethod
    def load(cls: "type[T_UnverifiedDataModel]", data: dict | None) -> "T_UnverifiedDataModel | None":
        if data is None:
            return None
        return cls._load(data)

    @classmethod
    def _type_by_field_name(cls) -> dict[str, type]:
        output: dict[str, type] = {}
        for field_ in fields(cls):
            type_ = field_.type
            if isinstance(type_, UnionType) or get_origin(type_) is Union:
                type_ = get_args(type_)[0]
            if isinstance(type_, str) and type_.startswith(cls.__name__):
                type_ = cls

            candidate: type
            if is_dataclass(type_):
                candidate = type_  # type: ignore[assignment]
            elif isinstance(type_, GenericAlias) and type_.__origin__ is list and is_dataclass(type_.__args__[0]):
                candidate = type_.__args__[0]  # type: ignore[assignment]

            # this handles prefixes
            elif isinstance(type_, GenericAlias) and type_.__origin__ is dict:
                candidate = type_  # type: ignore[assignment]
            else:
                continue

            output[field_.name] = candidate

        return output

    @classmethod
    def _load(cls, data: dict[str, Any]) -> Self:
        args: dict[str, Any] = {}
        field_type_by_name = cls._type_by_field_name()
        for field_name, field_ in cls._get_verified_cls().model_fields.items():
            field_type = field_type_by_name.get(field_name)
            if field_type is None:
                continue
            if field_name in data:
                value = data[field_name]
            elif field_.alias in data:
                value = data[field_.alias]
            else:
                continue

            # Handles the case where the field is a dataclass
            if hasattr(field_type, "_load"):
                if isinstance(value, dict):
                    args[field_name] = field_type._load(value)  # type: ignore[attr-defined]
                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    args[field_name] = [field_type._load(item) for item in value]  # type: ignore[attr-defined]
            # Handles the case where the field holds non-dataclass values, e.g. a prefixes dict
            else:
                args[field_name] = value

        return cls(**args)

    def _dataclass_fields(self) -> list[Field]:
        return list(fields(self))

    def as_verified_data_model(self) -> T_BaseDataModel:
        cls_ = self._get_verified_cls()
        return cls_.model_validate(self.dump())

    def dump(self) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for field_ in self._dataclass_fields():
            value = getattr(self, field_.name)
            if value is None:
                continue
            if hasattr(value, "dump"):
                output[field_.name] = value.dump()
            elif isinstance(value, list) and value and hasattr(value[0], "dump"):
                output[field_.name] = [item.dump() for item in value]
        return output


T_UnverifiedDataModel = TypeVar("T_UnverifiedDataModel", bound=UnverifiedDataModel)


@dataclass
class UnverifiedComponent(ABC, Generic[T_DataModel]):
    @classmethod
    @abstractmethod
    def _get_verified_cls(cls) -> type[T_DataModel]:
        raise NotImplementedError("This method should be implemented in the subclass.")

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> Self: ...

    @classmethod
    @overload
    def load(cls, data: list[dict[str, Any]]) -> list[Self]: ...

    @classmethod
    def load(cls, data: dict[str, Any] | list[dict[str, Any]] | None) -> Self | list[Self] | None:
        if data is None:
            return None
        if isinstance(data, list) or (isinstance(data, dict) and isinstance(data.get("data"), list)):
            items = cast(list[dict[str, Any]], data.get("data") if isinstance(data, dict) else data)
            return [loaded for item in items if (loaded := cls.load(item)) is not None]
        return cls._load(data)

    @classmethod
    def _load(cls, data: dict[str, Any]) -> Self:
        args: dict[str, Any] = {}
        for field_name, field_ in cls._get_verified_cls().model_fields.items():  # type: ignore[attr-defined]
            if field_.exclude:
                continue
            if field_name in data:
                args[field_name] = data[field_name]
            elif field_.alias in data:
                args[field_name] = data[field_.alias]
        return cls(**args)

    def dump(self, **kwargs: Any) -> dict[str, Any]:
        return {
            field_.alias or name: getattr(self, name)
            for name, field_ in self._get_verified_cls().model_fields.items()
            if not field_.exclude
        }

    def _repr_html_(self) -> str:
        return pd.DataFrame([self.dump()])._repr_html_()  # type: ignore[operator]
