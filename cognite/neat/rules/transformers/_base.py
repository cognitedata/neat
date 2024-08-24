from abc import ABC, abstractmethod
from collections.abc import MutableSequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from cognite.neat.issues import IssueList
from cognite.neat.issues.errors import NeatTypeError, NeatValueError
from cognite.neat.rules._shared import InputRules, Rules, T_Rules, VerifiedRules

T_RulesIn = TypeVar("T_RulesIn", bound=Rules)
T_RulesOut = TypeVar("T_RulesOut", bound=Rules)


@dataclass
class OutRules(Generic[T_Rules], ABC):
    """This is a base class for all rule states."""


@dataclass
class JustRules(OutRules[T_Rules]):
    """This represents a rule that exists"""

    rules: T_Rules


@dataclass
class MaybeRules(OutRules[T_Rules]):
    """This represents a rule that may or may not exist"""

    rules: T_Rules | None
    issues: IssueList


@dataclass
class ReadRules(OutRules[T_Rules]):
    """This represents a rule that does not exist"""

    rules: T_Rules
    read_context: dict[str, Any]


class RulesTransformer(ABC, Generic[T_RulesIn, T_RulesOut]):
    """This is the base class for all rule transformers.

    Note transformers follow the functional pattern Monad
    https://en.wikipedia.org/wiki/Monad_(functional_programming)
    """

    @abstractmethod
    def transform(self, rules: T_RulesIn | OutRules[T_RulesIn]) -> OutRules[T_RulesOut]:
        """Transform the input rules into the output rules."""
        raise NotImplementedError()

    @classmethod
    def _to_rules(cls, rules: T_RulesIn | OutRules[T_RulesIn]) -> T_RulesIn:
        if isinstance(rules, JustRules):
            return rules.rules
        elif isinstance(rules, MaybeRules):
            if rules.rules is None:
                raise NeatValueError("Rules is missing cannot convert")
            return rules.rules
        elif isinstance(rules, VerifiedRules | InputRules):
            return rules  # type: ignore[return-value]
        else:
            raise NeatTypeError(f"Unsupported type: {type(rules)}")


class RulesPipeline(list, MutableSequence[RulesTransformer], Generic[T_RulesIn, T_RulesOut]):
    def transform(self, rules: T_RulesIn | OutRules[T_RulesIn]) -> OutRules[T_RulesOut]:
        for transformer in self:
            rules = transformer.transform(rules)
        return rules  # type: ignore[return-value]

    def run(self, rules: T_RulesIn | OutRules[T_RulesIn]) -> T_RulesOut:
        output = self.transform(rules)
        if isinstance(output, MaybeRules):
            if output.rules is None:
                raise NeatValueError(f"Rule transformation failed: {output.issues}")
            return output.rules
        elif isinstance(output, JustRules):
            return output.rules
        else:
            raise NeatTypeError(f"Rule transformation failed: {output}")
