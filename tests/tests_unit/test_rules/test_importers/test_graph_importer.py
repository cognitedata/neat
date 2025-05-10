from collections.abc import Iterable

import pytest

from cognite.neat.core._data_model.importers import GraphImporter
from cognite.neat.core._data_model.models.information import InformationInputRules
from cognite.neat.core._shared import Triple
from cognite.neat.core._store import NeatGraphStore
from tests.data import GraphData


def graph_importer_test_cases() -> Iterable:
    """Generate test cases for the GraphImporter."""
    yield pytest.param(
        GraphData.car.TRIPLES,
        InformationInputRules.load(GraphData.car.get_care_rules().dump()),
        id="Car example",
    )


class TestGraphImporter:
    @pytest.mark.parametrize("triples, expected", list(graph_importer_test_cases()))
    def test_graph_importer(self, triples: list[Triple], expected: InformationInputRules) -> None:
        store = NeatGraphStore.from_oxi_local_store()
        store._add_triples(triples, store.default_named_graph)
        importer = GraphImporter(store)

        rules = importer.to_rules()
        actual = rules.rules
        assert actual is not None, "Failed to convert graph to rules"

        assert actual.as_verified_rules().dump() == expected.as_verified_rules().dump(), (
            "The rules generated from the graph do not match the expected rules."
        )
