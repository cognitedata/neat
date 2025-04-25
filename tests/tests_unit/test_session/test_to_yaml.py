from pathlib import Path

from cognite.neat import NeatSession
from cognite.neat.core._rules._shared import ReadRules
from cognite.neat.core._rules.importers import BaseImporter
from cognite.neat.core._rules.models import DMSInputRules
from tests.data import SchemaData


class RuleImporter(BaseImporter):
    def to_rules(self) -> ReadRules[DMSInputRules]:
        return ReadRules(SchemaData.NonNeatFormats.windturbine.INPUT_RULES, {})


class TestToYaml:
    def test_to_yaml(self, tmp_path: Path) -> None:
        neat = NeatSession()
        # Hack to read in model.
        neat._state.rule_store.import_rules(RuleImporter())

        neat.verify()
        neat.to.yaml(tmp_path, format="toolkit")

        files = list(tmp_path.rglob("*.yaml"))
        assert len(files) == 9
