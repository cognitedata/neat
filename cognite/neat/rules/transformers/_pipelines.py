from collections.abc import Iterable

from cognite.neat.rules._shared import MaybeRules, T_InputRules, T_VerifiedRules
from cognite.neat.rules.importers import BaseImporter

from ._base import RulesPipeline, RulesTransformer, T_RulesOut
from ._converters import ConvertAnyRules
from ._verification import VerifyAnyRules


class ImporterPipeline(RulesPipeline[T_InputRules, T_VerifiedRules]):
    """This is a standard pipeline that verifies, convert and return the rules from the importer."""

    def __init__(
        self,
        importer: BaseImporter[T_InputRules],
        items: Iterable[RulesTransformer[T_InputRules, T_VerifiedRules]] | None = None,
    ) -> None:
        super().__init__(items or [])
        self._importer = importer

    @classmethod
    def verify(cls, importer: BaseImporter[T_InputRules], out_type: type[T_VerifiedRules]) -> MaybeRules[T_RulesOut]:
        """This is a standard pipeline that verifies, convert and return the rules from the importer."""
        return cls(importer, [VerifyAnyRules(errors="continue"), ConvertAnyRules(out_type)]).try_execute()

    def try_execute(self) -> MaybeRules[T_RulesOut]:
        """Try to execute the pipeline from importer to rules."""
        rules = self._importer.to_rules()
        return self.try_transform(rules)
