from abc import ABC, abstractmethod
from collections.abc import MutableSequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from cognite.neat.issues import IssueList
from cognite.neat.issues.errors import NeatTypeError, NeatValueError
from cognite.neat.rules._shared import InputRules, Rules, T_Rules, VerifiedRules

T_RulesIn = TypeVar("T_RulesIn", bound=Rules)
T_RulesOut = TypeVar("T_RulesOut", bound=Rules)


@dataclass
class RulesState(Generic[T_Rules], ABC):
    """This is a base class for all rule states."""


@dataclass
class MaybeRule(RulesState[T_Rules]):
    """This represents a rule that may or may not exist"""

    rule: T_Rules | None
    issues: IssueList


@dataclass
class JustRule(RulesState[T_Rules]):
    """This represents a rule that exists"""

    rule: T_Rules


class RulesTransformer(ABC, Generic[T_RulesIn, T_RulesOut]):
    """This is the base class for all rule transformers.

    Note transformers follow the functional pattern Monad
    https://en.wikipedia.org/wiki/Monad_(functional_programming)
    """

    @abstractmethod
    def transform(self, rules: T_RulesIn | RulesState[T_RulesIn]) -> RulesState[T_RulesOut]:
        """Transform the input rules into the output rules."""
        raise NotImplementedError()

    @classmethod
    def _to_rules(cls, rules: T_RulesIn | RulesState[T_RulesIn]) -> T_RulesIn:
        if isinstance(rules, JustRule):
            return rules.rule
        elif isinstance(rules, MaybeRule):
            if rules.rule is None:
                raise NeatValueError("Rules is missing cannot convert")
            return rules.rule
        elif isinstance(rules, VerifiedRules | InputRules):
            return rules  # type: ignore[return-value]
        else:
            raise NeatTypeError(f"Unsupported type: {type(rules)}")


class RulesPipeline(list, MutableSequence[RulesTransformer], Generic[T_RulesIn, T_RulesOut]):
    def transform(self, rules: T_RulesIn | RulesState[T_RulesIn]) -> RulesState[T_RulesOut]:
        for transformer in self:
            rules = transformer.transform(rules)
        return rules  # type: ignore[return-value]

    def run(self, rules: T_RulesIn | RulesState[T_RulesIn]) -> T_RulesOut:
        output = self.transform(rules)
        if isinstance(output, MaybeRule):
            if output.rule is None:
                raise NeatValueError(f"Rule transformation failed: {output.issues}")
            return output.rule
        elif isinstance(output, JustRule):
            return output.rule
        else:
            raise NeatTypeError(f"Rule transformation failed: {output}")
