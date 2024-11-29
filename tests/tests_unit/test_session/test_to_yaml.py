from pathlib import Path

from rdflib import URIRef

from cognite.neat import NeatSession
from cognite.neat._issues import IssueList
from cognite.neat._rules._shared import ReadRules
from tests.data.windturbine import INPUT_RULES


class TestToYaml:
    def test_to_yaml(self, tmp_path: Path) -> None:
        neat = NeatSession()
        # Hack to read in model.
        neat._state.data_model._rules[URIRef("https://my_model")] = ReadRules(INPUT_RULES, IssueList(), {})

        neat.verify()
        neat.to.yaml(tmp_path, format="toolkit")

        files = list(tmp_path.rglob("*.yaml"))
        assert len(files) == 9
