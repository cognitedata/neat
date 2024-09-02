"""Module for base classes for the input models.

The philosophy of the input models is:

* Provide an easy way to input rules. The type hints are made to be human-friendly, for example, Literal instead of
  Enum.
* The .dump() method should fill out defaults and have shortcuts. For example, if the prefix is not provided for
  a class, then the prefix from the metadata is used. For views, if the class is not provided, it is assumed to
  be the same as the view.

The base classes are to make it easy to create the input models with default behavior. They are also used for
testing to ensure that input models correctly map to the verified rules models.
"""

import sys
from abc import ABC, abstractmethod
from dataclasses import Field, dataclass, fields, is_dataclass
from types import GenericAlias, UnionType
from typing import Any, Generic, TypeVar, Union, cast, get_args, get_origin, overload

from ._base_rules import BaseRules, RuleModel

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

T_BaseRules = TypeVar("T_BaseRules", bound=BaseRules)
T_RuleModel = TypeVar("T_RuleModel", bound=RuleModel)


@dataclass
class InputRules(Generic[T_BaseRules], ABC):
    """Input rules are raw data that is not yet validated."""

    @classmethod
    @abstractmethod
    def _get_verified_cls(cls) -> type[T_BaseRules]:
        raise NotImplementedError("This method should be implemented in the subclass.")

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> Self: ...

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    def load(cls, data: dict | None) -> Self | None:
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

            if is_dataclass(type_):
                candidate = type_
            elif isinstance(type_, GenericAlias) and type_.__origin__ is list and is_dataclass(type_.__args__[0]):
                candidate = type_.__args__[0]
            else:
                continue

            if hasattr(candidate, "_load"):
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

            if isinstance(value, dict):
                args[field_name] = field_type._load(value)  # type: ignore[attr-defined]
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                args[field_name] = [field_type._load(item) for item in value]  # type: ignore[attr-defined]
        return cls(**args)

    def _dataclass_fields(self) -> list[Field]:
        return list(fields(self))

    def as_rules(self) -> T_BaseRules:
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


@dataclass
class InputComponent(ABC, Generic[T_RuleModel]):
    @classmethod
    @abstractmethod
    def _get_verified_cls(cls) -> type[T_RuleModel]:
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

    def dump(self, **kwargs) -> dict[str, Any]:
        return {
            field_.alias or name: getattr(self, name)
            for name, field_ in self._get_verified_cls().model_fields.items()
            if not field_.exclude
        }
