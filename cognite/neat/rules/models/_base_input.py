"""Module for base classes for the input models."""

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
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
        _add_alias(data, cls._get_verified_cls())
        return cls._load(data)

    @classmethod
    @abstractmethod
    def _load(cls, data: dict[str, Any]) -> Self:
        raise NotImplementedError("This method should be implemented in the subclass.")

    def as_rules(self) -> T_BaseRules:
        cls_ = self._get_verified_cls()
        return cls_.model_validate(self.dump())

    @abstractmethod
    def dump(self) -> dict[str, Any]:
        raise NotImplementedError("This method should be implemented in the subclass.")


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
        _add_alias(data, cls._get_verified_cls())

        return cls._load(data)

    @classmethod
    @abstractmethod
    def _load(cls, data: dict[str, Any]) -> Self:
        raise NotImplementedError("This method should be implemented in the subclass.")
