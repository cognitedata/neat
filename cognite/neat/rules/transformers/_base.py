from abc import ABC, abstractmethod
from collections.abc import MutableSequence, Iterable
from typing import Generic, TypeVar, Any

from cognite.neat.issues.errors import NeatTypeError, NeatValueError
from cognite.neat.rules._shared import InputRules, JustRules, MaybeRules, OutRules, Rules, VerifiedRules
from cognite.neat.rules.importers import BaseImporter
from cognite.neat.rules.exporters import BaseExporter
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
    def __init__(self, items: Iterable[RulesTransformer[T_RulesIn, T_RulesOut]], importer: BaseImporter[T_RulesIn] | None = None) -> None:
        super().__init__(items)
        self._importer = importer

    @classmethod
    def from_importer(cls, importer: BaseImporter[T_RulesIn]) -> "RulesPipeline[T_RulesIn, T_RulesOut]":
        """Create a pipeline starting from an importer."""
        return cls([], importer=importer)

    def transform(self, rules: T_RulesIn | OutRules[T_RulesIn]) -> OutRules[T_RulesOut]:
        """Transform the input rules into the output rules."""
        for transformer in self:
            rules = transformer.transform(rules)
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

    def execute(self) -> T_RulesOut:
        """Execute the pipeline from importer to rules."""
        if self._importer is None:
            raise NeatTypeError("Cannot execute pipeline without an importer")
        rules = self._importer.to_rules()
        return self.run(rules)

    def try_execute(self) -> OutRules[T_RulesOut]:
        """Try to execute the pipeline from importer to rules."""
        if self._importer is None:
            raise NeatTypeError("Cannot execute pipeline without an importer")
        rules = self._importer.to_rules()
        return self.transform(rules)
