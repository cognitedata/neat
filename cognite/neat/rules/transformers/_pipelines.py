from collections.abc import Iterable

from cognite.neat.rules._shared import InputRules, MaybeRules, VerifiedRules
from cognite.neat.rules.importers import BaseImporter
from cognite.neat.rules.models import VERIFIED_RULES_BY_ROLE, RoleTypes

from ._base import RulesPipeline, RulesTransformer
from ._converters import ConvertToRules
from ._verification import VerifyAnyRules


class ImporterPipeline(RulesPipeline[InputRules, VerifiedRules]):
    """This is a standard pipeline that verifies, convert and return the rules from the importer."""

    def __init__(
        self,
        importer: BaseImporter[InputRules],
        items: Iterable[RulesTransformer[InputRules, VerifiedRules]] | None = None,
    ) -> None:
        super().__init__(items or [])
        self._importer = importer

    @classmethod
    def verify(cls, importer: BaseImporter, out_type: RoleTypes | None = None) -> MaybeRules[VerifiedRules]:
        """This is a standard pipeline that verifies, convert and return the rules from the importer.

        Args:
            importer: The importer to use.
            out_type: The type of rules to convert to. If None, the rules will not be converted.

        Returns:
            The verified rules.
        """
        items: list[RulesTransformer] = [VerifyAnyRules(errors="continue")]
        if out_type is not None:
            out_cls = VERIFIED_RULES_BY_ROLE[out_type]
            items.append(ConvertToRules(out_cls))
        return cls(importer, items).try_execute()

    def try_execute(self) -> MaybeRules[VerifiedRules]:
        """Try to execute the pipeline from importer to rules."""
        rules = self._importer.to_rules()
        return self.try_transform(rules)
