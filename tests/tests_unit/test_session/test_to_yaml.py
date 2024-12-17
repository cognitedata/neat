from pathlib import Path

from cognite.neat import NeatSession
from cognite.neat._issues import IssueList
from cognite.neat._rules._shared import ReadRules, T_InputRules
from cognite.neat._rules.importers import BaseImporter
from tests.data.windturbine import INPUT_RULES


class RuleImporter(BaseImporter):
    def to_rules(self) -> ReadRules[T_InputRules]:
        return ReadRules(INPUT_RULES, IssueList(), {})


class TestToYaml:
    def test_to_yaml(self, tmp_path: Path) -> None:
        neat = NeatSession()
        # Hack to read in model.
        neat._state.rule_store.write(RuleImporter())

        neat.verify()
        neat.to.yaml(tmp_path, format="toolkit")

        files = list(tmp_path.rglob("*.yaml"))
        assert len(files) == 9
