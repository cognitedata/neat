from pathlib import Path

from cognite.neat import NeatSession
from cognite.neat._issues import IssueList
from cognite.neat._rules._shared import ReadRules, T_InputRules
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.models import DMSInputRules
from tests.data.windturbine import INPUT_RULES


class RuleImporter(BaseImporter):
    def to_rules(self) -> ReadRules[DMSInputRules]:
        return ReadRules(INPUT_RULES, {})


class TestToYaml:
    def test_to_yaml(self, tmp_path: Path) -> None:
        neat = NeatSession()
        # Hack to read in model.
        neat._state.rule_store.import_(RuleImporter())

        neat.verify()
        neat.to.yaml(tmp_path, format="toolkit")

        files = list(tmp_path.rglob("*.yaml"))
        assert len(files) == 9
