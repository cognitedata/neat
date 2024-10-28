from abc import ABC, abstractmethod
from collections.abc import MutableSequence
from typing import Generic, TypeVar

from cognite.neat._issues import IssueList, NeatError
from cognite.neat._issues.errors import NeatTypeError, NeatValueError
from cognite.neat._rules._shared import (
    InputRules,
    JustRules,
    MaybeRules,
    OutRules,
    Rules,
    VerifiedRules,
)

T_RulesIn = TypeVar("T_RulesIn", bound=Rules)
T_RulesOut = TypeVar("T_RulesOut", bound=Rules)


class RulesTransformer(ABC, Generic[T_RulesIn, T_RulesOut]):
    """This is the base class for all rule transformers.

    Note transformers follow the functional pattern Monad
    https://en.wikipedia.org/wiki/Monad_(functional_programming)
    """

    @abstractmethod
    def transform(self, rules: T_RulesIn | OutRules[T_RulesIn]) -> OutRules[T_RulesOut]:
        """Transform the input rules into the output rules."""
        raise NotImplementedError()

    def try_transform(self, rules: MaybeRules[T_RulesIn]) -> MaybeRules[T_RulesOut]:
        """Try to transform the input rules into the output rules."""
        try:
            result = self.transform(rules)
        except NeatError:
            # Any error caught during transformation will be returned as issues
            return MaybeRules(None, rules.issues)
        issues = IssueList(rules.issues, title=rules.issues.title)
        if isinstance(result, MaybeRules):
            issues.extend(result.issues)
        return MaybeRules(result.get_rules(), issues)

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
        """Transform the input rules into the output rules."""
        for transformer in self:
            rules = transformer.transform(rules)
        return rules  # type: ignore[return-value]

    def try_transform(self, rules: MaybeRules[T_RulesIn]) -> MaybeRules[T_RulesOut]:
        """Try to transform the input rules into the output rules."""
        for transformer in self:
            rules = transformer.try_transform(rules)
        return rules  # type: ignore[return-value]

    def run(self, rules: T_RulesIn | OutRules[T_RulesIn]) -> T_RulesOut:
        """Run the pipeline from the input rules to the output rules."""
        output = self.transform(rules)
        if isinstance(output, MaybeRules):
            if output.rules is None:
                raise NeatValueError(f"Rule transformation failed: {output.issues}")
            return output.rules
        elif isinstance(output, JustRules):
            return output.rules
        else:
            raise NeatTypeError(f"Rule transformation failed: {output}")
