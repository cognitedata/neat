"""Module for base classes for the input models."""

import sys
from abc import ABC, abstractmethod
from dataclasses import Field, dataclass, fields
from typing import Any, Generic, TypeVar, cast, overload

from pydantic import BaseModel

from ._base import BaseRules, RuleModel

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

T_BaseRules = TypeVar("T_BaseRules", bound=BaseRules)
T_RuleModel = TypeVar("T_RuleModel", bound=RuleModel)


def _add_alias(data: dict[str, Any], base_model: type[BaseModel]) -> None:
    for field_name, field_ in base_model.model_fields.items():
        if field_name not in data and field_.alias in data:
            data[field_name] = data[field_.alias]


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
    def _load(cls, data: dict[str, Any]) -> Self:
        args: dict[str, Any] = {}
        field_type_by_name = {field_.name: field_.type for field_ in fields(cls)}
        for field_name, field_ in cls._get_verified_cls().model_fields.items():
            field_type = field_type_by_name.get(field_name)
            if field_name in data:
                args[field_name] = field_type._load(data[field_name])
            elif field_.alias in data:
                args[field_name] = field_type._load(data[field_.alias])
        return cls(**args)

    def _dataclass_fields(self) -> list[Field]:
        return list(fields(self))

    def as_rules(self) -> T_BaseRules:
        cls_ = self._get_verified_cls()
        return cls_.model_validate(self.dump())

    def dump(self) -> dict[str, Any]:
        return {field_.name: getattr(self, field_.name).dump() for field_ in self._dataclass_fields()}


@dataclass
class InputComponent(ABC):
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
        for field_name, field_ in cls._get_verified_cls().model_fields.items():
            if field_name in data:
                args[field_name] = data[field_name]
            elif field_.alias in data:
                args[field_name] = data[field_.alias]
        return cls(**args)
