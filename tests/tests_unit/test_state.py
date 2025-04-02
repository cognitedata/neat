from collections.abc import Iterable
from pathlib import Path

import pytest
from rdflib import Graph

from cognite.neat._graph.extractors import BaseExtractor
from cognite.neat._graph.loaders import BaseLoader
from cognite.neat._graph.loaders._base import _END_OF_CLASS, _START_OF_CLASS
from cognite.neat._graph.transformers import BaseTransformer
from cognite.neat._issues import NeatIssue
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.exporters import BaseExporter
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.models import DMSInputRules, InformationInputRules, InformationRules
from cognite.neat._rules.models.dms import DMSInputContainer, DMSInputMetadata, DMSInputProperty, DMSInputView
from cognite.neat._rules.models.information import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
)
from cognite.neat._rules.transformers import RulesTransformer
from cognite.neat._shared import Triple
from cognite.neat._state import Action, NeatState


class DummyInfoImporter(BaseImporter):
    def to_rules(self) -> ReadRules[InformationInputRules]:
        return ReadRules(
            rules=InformationInputRules(
                metadata=InformationInputMetadata("my_space", "MySpace", "v1", "doctrino"),
                properties=[InformationInputProperty("Thing", "name", "text")],
                classes=[InformationInputClass("Thing")],
            ),
            read_context={},
        )


class DummyDMSImporter(BaseImporter):
    def to_rules(self) -> ReadRules[DMSInputRules]:
        return ReadRules(
            rules=DMSInputRules(
                metadata=DMSInputMetadata("my_space", "MySpace", "v1", "doctrino"),
                properties=[DMSInputProperty("Thing", "name", "text", container="Thing", container_property="name")],
                views=[DMSInputView("Thing")],
                containers=[DMSInputContainer("Thing")],
            ),
            read_context={},
        )


class NoOptExporter(BaseExporter[InformationRules, str]):
    def export_to_file(self, rules: InformationRules, filepath: Path) -> None:
        return None

    def export(self, rules: InformationRules) -> str:
        return ""


class NoOptExtractor(BaseExtractor):
    def extract(self) -> Iterable[Triple]:
        return []


class NoOptTransformer(BaseTransformer):
    def transform(self, graph: Graph) -> None:
        return None


class NoOptRulesTransformer(RulesTransformer[InformationRules, InformationInputRules]):
    def transform(self, rules: InformationRules) -> InformationRules:
        return rules


class NoOptLoader(BaseLoader[str]):
    def _load(
        self, stop_on_exception: bool = False
    ) -> Iterable[str | NeatIssue | type[_END_OF_CLASS] | _START_OF_CLASS]:
        yield ""
        return

    def write_to_file(self, filepath: Path) -> None:
        return None


@pytest.fixture(scope="function")
def empty_state() -> NeatState:
    """Fixture for creating an empty NeatState instance."""
    return NeatState()


class TestNeatState:
    @pytest.mark.parametrize(
        "actions, expected_state",
        [
            pytest.param([DummyInfoImporter()], "Conceptual", id="Import information rules"),
            pytest.param([NoOptExtractor()], "Instances", id="Extract instances"),
        ],
    )
    def test_valid_change(self, actions: list[Action], expected_state: str, empty_state: NeatState) -> None:
        for action in actions:
            _ = empty_state.change(action)

        assert empty_state.status == expected_state, "State did not change as expected."
