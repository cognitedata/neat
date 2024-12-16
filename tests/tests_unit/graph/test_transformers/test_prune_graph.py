from collections.abc import Iterable

import pytest
from _pytest.mark import ParameterSet
from rdflib import RDF

from cognite.neat._constants import get_default_prefixes_and_namespaces
from cognite.neat._graph.transformers import PruneDeadEndEdges
from cognite.neat._shared import Triple
from cognite.neat._store import NeatGraphStore


def generate_test_parameters_unknown_types() -> Iterable[ParameterSet]:
    namespace = get_default_prefixes_and_namespaces()["iodd"]

    original_triples = [
        (namespace["Device-ID"], RDF.type, namespace["Device"]),
        (
            namespace["Device-ID"],
            namespace["someProperty"],
            namespace["Not-an-existing-node-ID"],
        ),
        (
            namespace["Device-ID"],
            namespace["someProperty"],
            namespace["An-existing-node-ID"],
        ),
        (namespace["An-existing-node-ID"], RDF.type, namespace["AnotherDevice"]),
    ]

    expected_triples = [
        (namespace["Device-ID"], RDF.type, namespace["Device"]),
        (
            namespace["Device-ID"],
            namespace["someProperty"],
            namespace["An-existing-node-ID"],
        ),
        (namespace["An-existing-node-ID"], RDF.type, namespace["AnotherDevice"]),
    ]
    expected_triples = [[str(item) for item in triple] for triple in expected_triples]
    expected_triples.sort()
    triples_removed = 1

    yield pytest.param(
        original_triples,
        expected_triples,
        triples_removed,
        id="Flatten with new predicate, literal to URIRef, delete intermediate node",
    )


class TestPruneGraph:
    @pytest.mark.parametrize(
        "original_triples, expected_triples, triples_removed",
        generate_test_parameters_unknown_types(),
    )
    def test_prune_instances_of_unknown_type(
        self, original_triples: list[Triple], expected_triples: list[Triple], triples_removed: int
    ):
        store = NeatGraphStore.from_memory_store()

        store._add_triples(original_triples)

        PruneDeadEndEdges().transform(store.graph)

        triples_after = [triple for triple in store.graph.triples((None, None, None))]
        triples_after = [[str(item) for item in triple] for triple in triples_after]
        # Sort the triples to ensure deterministic output
        triples_after.sort()

        assert triples_after == expected_triples
        assert len(triples_after) == len(expected_triples)

    def test_prune_dead_end_edges(self): ...

    def test_prune_types(self): ...
