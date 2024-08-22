from abc import ABC, abstractmethod
from collections.abc import MutableSequence
from typing import Generic, TypeVar

from cognite.neat.rules._shared import Rules

T_RulesIn = TypeVar("T_RulesIn", bound=Rules)
T_RulesOut = TypeVar("T_RulesOut", bound=Rules)


class RulesTransformer(ABC, Generic[T_RulesIn, T_RulesOut]):
    """This is the base class for all rule transformers."""

    @abstractmethod
    def transform(self, rules: T_RulesIn) -> T_RulesOut:
        """Transform the input rules into the output rules."""
        raise NotImplementedError()


class RulesPipeline(list, MutableSequence[RulesTransformer], Generic[T_RulesIn, T_RulesOut]):
    def run(self, rules: T_RulesIn) -> T_RulesOut:
        for transformer in self:
            rules = transformer.transform(rules)
        return rules  # type: ignore[return-value]
