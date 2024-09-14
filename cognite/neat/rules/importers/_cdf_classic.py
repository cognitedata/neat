from cognite.neat.issues import IssueList
from cognite.neat.rules._shared import ReadRules
from cognite.neat.rules.models import DMSInputRules
from cognite.neat.rules.models.dms import DMSInputMetadata
from cognite.neat.store import NeatGraphStore

from ._base import BaseImporter


class CDFClassicGraphImporter(BaseImporter[DMSInputRules]):
    def __init__(self, store: NeatGraphStore, core_model: DMSInputRules | None = None) -> None:
        self._store = store
        self._core_model = core_model

    def to_rules(self) -> ReadRules[DMSInputRules]:
        issues = IssueList()
        rules = DMSInputRules(
            metadata=DMSInputMetadata.load(self._default_metadata()),
            properties=[],
            views=[],
            containers=[],
            nodes=[],
            reference=self._core_model,
        )
        self._add_source_system(rules)
        self._add_dataset(rules)
        self._add_asset(rules)
        self._add_event(rules)
        self._add_sequence(rules)
        self._add_file(rules)

        return ReadRules(rules, issues, read_context={})

    def _add_source_system(self, rules: DMSInputRules) -> None:
        pass

    def _add_dataset(self, rules: DMSInputRules) -> None:
        pass

    def _add_asset(self, rules: DMSInputRules) -> None:
        pass

    def _add_event(self, rules: DMSInputRules) -> None:
        pass

    def _add_sequence(self, rules: DMSInputRules) -> None:
        pass

    def _add_file(self, rules: DMSInputRules) -> None:
        pass
