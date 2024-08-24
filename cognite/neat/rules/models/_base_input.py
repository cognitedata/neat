"""Module for base classes for the input models."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from ._base import BaseRules

T_BaseRules = TypeVar("T_BaseRules", bound=BaseRules)


@dataclass
class InputRules(Generic[T_BaseRules], ABC):
    """Input rules are raw data that is not yet validated."""

    @abstractmethod
    def _get_verified_cls(self) -> type[T_BaseRules]:
        raise NotImplementedError("This method should be implemented in the subclass.")
