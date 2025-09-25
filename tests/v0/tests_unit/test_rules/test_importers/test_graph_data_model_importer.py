from collections.abc import Iterable

import pytest
from rdflib import RDF, RDFS, Literal, Namespace

from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._data_model.importers import GraphImporter
from cognite.neat.v0.core._data_model.models.conceptual import (
    UnverifiedConcept,
    UnverifiedConceptualDataModel,
    UnverifiedConceptualMetadata,
    UnverifiedConceptualProperty,
)
from cognite.neat.v0.core._issues.warnings import NeatValueWarning
from cognite.neat.v0.core._shared import Triple
from cognite.neat.v0.core._store import NeatInstanceStore
from tests.v0.data import GraphData


def graph_importer_test_cases() -> Iterable:
    """Generate test cases for the GraphImporter."""
    car_conceptual = UnverifiedConceptualDataModel.load(GraphData.car.get_care_rules().dump())
    yield pytest.param(
        GraphData.car.TRIPLES,
        car_conceptual,
        id="Car example",
    )

    instance_space = Namespace("http://example.com/instance_space/")
    schema_space = DEFAULT_NAMESPACE
    expected_model = UnverifiedConceptualDataModel(
        metadata=UnverifiedConceptualMetadata("my_space", "my_model", "v1", "doctrino"),
        properties=[
            UnverifiedConceptualProperty(
                "Car", "manufacturer", "#N/A", max_count=1, instance_source=schema_space["manufacturer"]
            ),
            UnverifiedConceptualProperty(
                "Car", "weight", "integer, text", max_count=1, instance_source=schema_space["weight"]
            ),
        ],
        concepts=[
            UnverifiedConcept("Vehicle"),
            UnverifiedConcept("Car", implements="Vehicle", instance_source=schema_space["Car"]),
        ],
        prefixes={},
    )

    my_car = instance_space["my_car"]
    car_type = schema_space["Car"]
    my_car2 = instance_space["my_car2"]
    yield pytest.param(
        [
            (car_type, RDFS.subClassOf, schema_space["Vehicle"]),
            (my_car, RDF.type, car_type),
            (my_car, schema_space["weight"], Literal(100)),
            (my_car2, RDF.type, car_type),
            (my_car2, schema_space["weight"], Literal("105kg")),
            (my_car2, schema_space["manufacturer"], instance_space["Toyota"]),
        ],
        expected_model,
        id="Parent, multi-value, and unknown value type.",
    )


def graph_importer_warning_test_cases() -> Iterable:
    empty_model = UnverifiedConceptualDataModel(
        metadata=UnverifiedConceptualMetadata("my_space", "my_model", "v1", "doctrino"),
        properties=[],
        concepts=[],
        prefixes={},
    )
    yield pytest.param(
        [],
        empty_model,
        NeatValueWarning("Cannot infer data model. No data found in the graph."),
        id="Empty graph",
    )
    instance_space = Namespace("http://example.com/instance_space/")
    schema_space = DEFAULT_NAMESPACE
    yield pytest.param(
        [
            (instance_space["car1"], schema_space["wheelCount"], Literal(4)),
            (instance_space["car2"], schema_space["weight"], Literal(100)),
        ],
        empty_model,
        NeatValueWarning("Cannot infer data model. No RDF.type triples found in the graph."),
        id="Graph with no RDF.type triples",
    )


class TestGraphImporter:
    @pytest.mark.parametrize("triples, expected", list(graph_importer_test_cases()))
    def test_graph_importer(self, triples: list[Triple], expected: UnverifiedConceptualDataModel) -> None:
        store = NeatInstanceStore.from_oxi_local_store()
        store._add_triples(triples, store.default_named_graph)
        metadata = expected.metadata
        data_model_id = (metadata.space, metadata.external_id, metadata.version)
        importer = GraphImporter(store, data_model_id)

        rules = importer.to_data_model()
        actual = rules.unverified_data_model
        assert actual is not None, "Failed to convert graph to rules"

        # Prefixes are set to defaults upon loading a data model
        # while the GraphImporter uses the prefixes from the graph
        exclude = {"metadata": {"creator", "created", "updated", "description", "name"}, "prefixes": True}
        assert actual.as_verified_data_model().dump(exclude=exclude) == expected.as_verified_data_model().dump(
            exclude=exclude
        ), "The rules generated from the graph do not match the expected rules."

    @pytest.mark.parametrize("triples, expected_model, expected_warning", list(graph_importer_warning_test_cases()))
    def test_graph_importer_warnings(
        self, triples: list[Triple], expected_model: UnverifiedConceptualDataModel, expected_warning: NeatValueWarning
    ) -> None:
        store = NeatInstanceStore.from_oxi_local_store()
        store._add_triples(triples, store.default_named_graph)
        metadata = expected_model.metadata
        data_model_id = (metadata.space, metadata.external_id, metadata.version)
        importer = GraphImporter(store, data_model_id)

        with pytest.warns(NeatValueWarning) as record:
            rules = importer.to_data_model()
            actual = rules.unverified_data_model
            assert actual is not None, "Failed to convert graph to rules"
            assert len(record) == 1
            assert str(record[0].message) == str(expected_warning)
