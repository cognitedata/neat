from collections.abc import Iterable

from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules._shared import InputRules, MaybeRules, VerifiedRules
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.models import VERIFIED_RULES_BY_ROLE, RoleTypes

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
    def _create_pipeline(cls, importer: BaseImporter[InputRules], role: RoleTypes | None = None) -> "ImporterPipeline":
        items: list[RulesTransformer] = [VerifyAnyRules(errors="continue")]
        if role is not None:
            out_cls = VERIFIED_RULES_BY_ROLE[role]
            items.append(ConvertToRules(out_cls))
        return cls(importer, items)

    @classmethod
    def try_verify(cls, importer: BaseImporter, role: RoleTypes | None = None) -> MaybeRules[VerifiedRules]:
        """This is a standard pipeline that verifies, convert and return the rules from the importer.

        Args:
            importer: The importer to use.
            role: The type of rules to convert to. If None, the rules will not be converted.

        Returns:
            The verified rules.
        """
        return cls._create_pipeline(importer, role).try_execute()

    @classmethod
    def verify(cls, importer: BaseImporter, role: RoleTypes | None = None) -> VerifiedRules:
        """Verify the rules."""
        return cls._create_pipeline(importer, role).execute()

    def try_execute(self) -> MaybeRules[VerifiedRules]:
        """Try to execute the pipeline from importer to rules."""
        rules = self._importer.to_rules()
        return self.try_transform(rules)

    def execute(self) -> VerifiedRules:
        """Execute the pipeline from importer to rules."""
        rules = self._importer.to_rules()
        out = self.transform(rules)
        if isinstance(out, MaybeRules) and out.rules is None:
            raise out.issues.as_errors("Failed to convert rules")

        rules = out.get_rules()
        if rules is None:
            raise NeatValueError("Rules is missing cannot convert")
        return rules
