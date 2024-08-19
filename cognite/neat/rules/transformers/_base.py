from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from cognite.neat.rules._shared import Rules

T_RulesIn = TypeVar("T_RulesIn", bound=Rules)
T_RulesOut = TypeVar("T_RulesOut", bound=Rules)


class RulesTransformer(ABC, Generic[T_RulesIn, T_RulesOut]):
    """This is the base class for all rule transformers."""

    @abstractmethod
    def transform(self, rules: T_RulesIn) -> T_RulesOut:
        raise NotImplementedError()
