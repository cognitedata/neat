from collections.abc import Iterable

import pytest
from _pytest.mark import ParameterSet
from rdflib import Literal, Namespace, URIRef

from cognite.neat._graph.transformers._prune_graph import AttachPropertyFromTargetToSource
from cognite.neat._shared import Triple
from cognite.neat._store import NeatGraphStore

RDF_TYPE = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")


def generate_test_parameters_delete_target_node() -> Iterable[ParameterSet]:
    target_property = "value"
    target_property_holding_new_property_name = "description"
    namespace = Namespace("http://www.io-link.com/IODD/2010/10/")
    target_node_type = namespace["TextObject"]

    triples_keep_old_predicate = [
        (namespace["Text-Destination-ID"], RDF_TYPE, namespace["TextObject"]),
        (namespace["Text-Destination-ID"], namespace["value"], Literal("Vacuum system self-check completed.")),
        (namespace["Device-Source-ID"], namespace["textProperty"], namespace["Text-Destination-ID"]),
        (namespace["Device-Source-ID"], RDF_TYPE, namespace["Device"]),
    ]

    expected_triples_keep_old_predicate = [
        (namespace["Device-Source-ID"], RDF_TYPE, namespace["Device"]),
        (namespace["Device-Source-ID"], namespace["textProperty"], Literal("Vacuum system self-check completed.")),
    ]

    expected_triples_keep_old_predicate = [
        [str(item) for item in triple] for triple in expected_triples_keep_old_predicate
    ]
    expected_triples_keep_old_predicate.sort()

    yield pytest.param(
        triples_keep_old_predicate,
        target_node_type,
        namespace,
        target_property,
        None,
        expected_triples_keep_old_predicate,
        id="Flatten and keep old predicate and delete intermediate node",
    )

    triples_new_predicate = [
        (namespace["Text-Destination-ID"], RDF_TYPE, namespace["TextObject"]),
        (namespace["Text-Destination-ID"], namespace["value"], Literal("Vacuum system self-check completed.")),
        (namespace["Text-Destination-ID"], namespace["description"], Literal("vacuum status")),
        (namespace["Device-Source-ID"], namespace["textProperty"], namespace["Text-Destination-ID"]),
        (namespace["Device-Source-ID"], RDF_TYPE, namespace["Device"]),
    ]

    expected_triples_new_predicate = [
        (namespace["Device-Source-ID"], RDF_TYPE, namespace["Device"]),
        (namespace["Device-Source-ID"], namespace["vacuumStatus"], Literal("Vacuum system self-check completed.")),
    ]

    expected_triples_new_predicate = [[str(item) for item in triple] for triple in expected_triples_new_predicate]
    expected_triples_new_predicate.sort()

    yield pytest.param(
        triples_new_predicate,
        target_node_type,
        namespace,
        target_property,
        target_property_holding_new_property_name,
        expected_triples_new_predicate,
        id="Flatten with new predicate and delete intermediate node",
    )


def generate_test_parameters_keep_target_node() -> Iterable[ParameterSet]:
    target_property = "value"
    target_property_holding_new_property_name = "description"
    namespace = Namespace("http://www.io-link.com/IODD/2010/10/")
    destination_node_type = namespace["TextObject"]

    triples_keep_old_predicate = [
        (namespace["Text-Destination-ID"], RDF_TYPE, namespace["TextObject"]),
        (namespace["Text-Destination-ID"], namespace["value"], Literal("Vacuum system self-check completed.")),
        (namespace["Device-Source-ID"], namespace["textProperty"], namespace["Text-Destination-ID"]),
        (namespace["Device-Source-ID"], RDF_TYPE, namespace["Device"]),
    ]

    expected_triples_keep_old_predicate = [
        (namespace["Device-Source-ID"], RDF_TYPE, namespace["Device"]),
        (namespace["Device-Source-ID"], namespace["textProperty"], Literal("Vacuum system self-check completed.")),
        (namespace["Text-Destination-ID"], RDF_TYPE, namespace["TextObject"]),
        (namespace["Text-Destination-ID"], namespace["value"], Literal("Vacuum system self-check completed.")),
    ]

    expected_triples_keep_old_predicate = [
        [str(item) for item in triple] for triple in expected_triples_keep_old_predicate
    ]
    expected_triples_keep_old_predicate.sort()

    yield pytest.param(
        triples_keep_old_predicate,
        destination_node_type,
        namespace,
        target_property,
        None,
        expected_triples_keep_old_predicate,
        id="Flatten and keep old predicate and keep intermediate node",
    )

    triples_new_predicate = [
        (namespace["Text-Destination-ID"], RDF_TYPE, namespace["TextObject"]),
        (namespace["Text-Destination-ID"], namespace["value"], Literal("Vacuum system self-check completed.")),
        (namespace["Text-Destination-ID"], namespace["description"], Literal("vacuum status")),
        (namespace["Device-Source-ID"], namespace["textProperty"], namespace["Text-Destination-ID"]),
        (namespace["Device-Source-ID"], RDF_TYPE, namespace["Device"]),
    ]

    expected_triples_new_predicate = [
        (namespace["Device-Source-ID"], RDF_TYPE, namespace["Device"]),
        (namespace["Device-Source-ID"], namespace["vacuumStatus"], Literal("Vacuum system self-check completed.")),
        # The intermediate target node and its properties are kept in the graph
        (namespace["Text-Destination-ID"], RDF_TYPE, namespace["TextObject"]),
        (namespace["Text-Destination-ID"], namespace["value"], Literal("Vacuum system self-check completed.")),
        (namespace["Text-Destination-ID"], namespace["description"], Literal("vacuum status")),
    ]

    expected_triples_new_predicate = [[str(item) for item in triple] for triple in expected_triples_new_predicate]
    expected_triples_new_predicate.sort()

    yield pytest.param(
        triples_new_predicate,
        destination_node_type,
        namespace,
        target_property,
        target_property_holding_new_property_name,
        expected_triples_new_predicate,
        id="Flatten with new predicate and keep intermediate node",
    )


class TestAttachPropertyFromTargetToSource:
    @pytest.mark.parametrize(
        "triples, target_node_type, namespace, "
        "target_property, target_property_holding_new_property_name, expected_triples",
        list(generate_test_parameters_delete_target_node()),
    )
    def test_two_hop_flattener_delete_connecting_node(
        self,
        triples: list[Triple],
        target_node_type: URIRef,
        namespace: Namespace,
        target_property: str,
        target_property_holding_new_property_name: str | None,
        expected_triples: list[Triple],
    ):
        store = NeatGraphStore.from_memory_store()

        store._add_triples(triples)

        flatten_dexpi_graph = AttachPropertyFromTargetToSource(
            target_node_type=target_node_type,
            namespace=namespace,
            target_property_holding_new_property_name=target_property_holding_new_property_name,
            target_property=target_property,
            delete_target_node=True,
        )

        flatten_dexpi_graph.transform(store.graph)

        triples_after = [triple for triple in store.graph.triples((None, None, None))]
        triples_after = [[str(item) for item in triple] for triple in triples_after]
        # Sort the triples to ensure deterministic output
        triples_after.sort()

        assert len(triples_after) == len(expected_triples)
        assert triples_after == expected_triples

    @pytest.mark.parametrize(
        "triples, target_node_type, namespace, "
        "target_property, target_property_holding_new_property_name, expected_triples",
        list(generate_test_parameters_keep_target_node()),
    )
    def test_two_hop_flattener_keep_connecting_node(
        self,
        triples: list[Triple],
        target_node_type: URIRef,
        namespace: Namespace,
        target_property: str,
        target_property_holding_new_property_name: str | None,
        expected_triples: list[Triple],
    ):
        store = NeatGraphStore.from_memory_store()

        store._add_triples(triples)

        flatten_dexpi_graph = AttachPropertyFromTargetToSource(
            target_node_type=target_node_type,
            namespace=namespace,
            target_property=target_property,
            target_property_holding_new_property_name=target_property_holding_new_property_name,
            delete_target_node=False,
        )

        flatten_dexpi_graph.transform(store.graph)

        triples_after = [triple for triple in store.graph.triples((None, None, None))]
        triples_after = [[str(item) for item in triple] for triple in triples_after]
        # Sort the triples to ensure deterministic output
        triples_after.sort()

        assert len(triples_after) == len(expected_triples)
        assert triples_after == expected_triples
