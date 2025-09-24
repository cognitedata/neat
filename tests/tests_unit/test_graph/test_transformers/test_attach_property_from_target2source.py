from collections.abc import Iterable

import pytest
from _pytest.mark import ParameterSet
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.v0.core._constants import get_default_prefixes_and_namespaces
from cognite.neat.v0.core._instances.transformers._prune_graph import (
    AttachPropertyFromTargetToSource,
)
from cognite.neat.v0.core._shared import Triple
from cognite.neat.v0.core._store import NeatInstanceStore


def generate_test_parameters_delete_target_node() -> Iterable[ParameterSet]:
    namespace = get_default_prefixes_and_namespaces()["iodd"]
    target_node_type = namespace["TextObject"]
    target_property = namespace["value"]
    target_property_holding_new_property = namespace["description"]

    # YIELD Flatten and keep old predicate and delete intermediate node"
    original_triples = [
        (namespace["Device-Source-ID"], RDF.type, namespace["Device"]),
        (
            namespace["Device-Source-ID"],
            namespace["textProperty"],
            namespace["Text-Destination-ID"],
        ),
        (namespace["Text-Destination-ID"], RDF.type, target_node_type),
        (
            namespace["Text-Destination-ID"],
            target_property,
            Literal("SomethingThatCanBeNode"),
        ),
    ]

    expected_triples_keep_old_predicate = [
        (namespace["Device-Source-ID"], RDF.type, namespace["Device"]),
        (
            namespace["Device-Source-ID"],
            namespace["textProperty"],
            Literal("SomethingThatCanBeNode"),
        ),
    ]

    expected_triples_keep_old_predicate = [
        [str(item) for item in triple] for triple in expected_triples_keep_old_predicate
    ]
    expected_triples_keep_old_predicate.sort()

    yield pytest.param(
        original_triples,
        target_node_type,
        namespace,
        target_property,
        None,
        expected_triples_keep_old_predicate,
        False,
        id="Flatten and keep old predicate and delete intermediate node",
    )

    original_triples.append(
        (
            namespace["Text-Destination-ID"],
            target_property_holding_new_property,
            Literal("vacuum status"),
        ),
    )

    expected_triples_new_predicate = [
        (namespace["Device-Source-ID"], RDF.type, namespace["Device"]),
        (
            namespace["Device-Source-ID"],
            namespace["vacuumStatus"],
            Literal("SomethingThatCanBeNode"),
        ),
    ]

    expected_triples_new_predicate = [[str(item) for item in triple] for triple in expected_triples_new_predicate]
    expected_triples_new_predicate.sort()

    yield pytest.param(
        original_triples,
        target_node_type,
        namespace,
        target_property,
        target_property_holding_new_property,
        expected_triples_new_predicate,
        False,
        id="Flatten with new predicate and delete intermediate node",
    )

    original_extended = original_triples.copy()

    original_extended.extend(
        [
            (
                namespace["Text-Destination-ID"],
                target_property_holding_new_property,
                Literal("vacuum status"),
            ),
            (
                namespace["SomethingThatCanBeNode"],
                RDF.type,
                namespace["Node"],
            ),
        ]
    )

    expected_triples_new_predicate = [
        (namespace["Device-Source-ID"], RDF.type, namespace["Device"]),
        (
            namespace["Device-Source-ID"],
            namespace["vacuumStatus"],
            namespace["SomethingThatCanBeNode"],
        ),
        (
            namespace["SomethingThatCanBeNode"],
            RDF.type,
            namespace["Node"],
        ),
    ]

    expected_triples_new_predicate = [[str(item) for item in triple] for triple in expected_triples_new_predicate]
    expected_triples_new_predicate.sort()

    yield pytest.param(
        original_extended,
        target_node_type,
        namespace,
        target_property,
        target_property_holding_new_property,
        expected_triples_new_predicate,
        True,
        id="Flatten with new predicate, literal to URIRef, delete intermediate node",
    )


def generate_test_parameters_keep_target_node() -> Iterable[ParameterSet]:
    namespace = get_default_prefixes_and_namespaces()["iodd"]
    target_property = namespace["value"]
    target_property_holding_new_property = namespace["description"]
    target_node_type = namespace["TextObject"]

    original_triples = [
        (namespace["Device-Source-ID"], RDF.type, namespace["Device"]),
        (
            namespace["Device-Source-ID"],
            namespace["textProperty"],
            namespace["Text-Destination-ID"],
        ),
        (namespace["Text-Destination-ID"], RDF.type, target_node_type),
        (
            namespace["Text-Destination-ID"],
            target_property,
            Literal("SomethingThatCanBeNode"),
        ),
    ]

    expected_triples_keep_old_predicate = [
        (namespace["Device-Source-ID"], RDF.type, namespace["Device"]),
        (
            namespace["Device-Source-ID"],
            namespace["textProperty"],
            Literal("SomethingThatCanBeNode"),
        ),
        (namespace["Text-Destination-ID"], RDF.type, target_node_type),
        (
            namespace["Text-Destination-ID"],
            target_property,
            Literal("SomethingThatCanBeNode"),
        ),
    ]

    expected_triples_keep_old_predicate = [
        [str(item) for item in triple] for triple in expected_triples_keep_old_predicate
    ]
    expected_triples_keep_old_predicate.sort()

    yield pytest.param(
        original_triples.copy(),
        target_node_type,
        namespace,
        target_property,
        None,
        expected_triples_keep_old_predicate,
        False,
        id="Flatten and keep old predicate and keep intermediate node",
    )

    triples_new_predicate = original_triples.copy()

    triples_new_predicate.append(
        (
            namespace["Text-Destination-ID"],
            target_property_holding_new_property,
            Literal("vacuum status"),
        )
    )

    expected_triples_new_predicate = [
        (namespace["Device-Source-ID"], RDF.type, namespace["Device"]),
        (
            namespace["Device-Source-ID"],
            namespace["vacuumStatus"],
            Literal("SomethingThatCanBeNode"),
        ),
        # The intermediate target node and its properties are kept in the graph
        (namespace["Text-Destination-ID"], RDF.type, target_node_type),
        (
            namespace["Text-Destination-ID"],
            target_property,
            Literal("SomethingThatCanBeNode"),
        ),
        (
            namespace["Text-Destination-ID"],
            target_property_holding_new_property,
            Literal("vacuum status"),
        ),
    ]

    expected_triples_new_predicate = [[str(item) for item in triple] for triple in expected_triples_new_predicate]
    expected_triples_new_predicate.sort()

    yield pytest.param(
        triples_new_predicate,
        target_node_type,
        namespace,
        target_property,
        target_property_holding_new_property,
        expected_triples_new_predicate,
        False,
        id="Flatten with new predicate and keep intermediate node",
    )

    original_extended = original_triples.copy()

    original_extended.extend(
        [
            (
                namespace["Text-Destination-ID"],
                target_property_holding_new_property,
                Literal("vacuum status"),
            ),
            (
                namespace["SomethingThatCanBeNode"],
                RDF.type,
                namespace["Node"],
            ),
        ]
    )

    expected_triples_new_predicate = [
        (namespace["Device-Source-ID"], RDF.type, namespace["Device"]),
        (
            namespace["Device-Source-ID"],
            namespace["vacuumStatus"],
            namespace["SomethingThatCanBeNode"],
        ),
        # The intermediate target node and its properties are kept in the graph
        (namespace["Text-Destination-ID"], RDF.type, target_node_type),
        (
            namespace["Text-Destination-ID"],
            target_property,
            Literal("SomethingThatCanBeNode"),
        ),
        (
            namespace["Text-Destination-ID"],
            target_property_holding_new_property,
            Literal("vacuum status"),
        ),
        (
            namespace["SomethingThatCanBeNode"],
            RDF.type,
            namespace["Node"],
        ),
    ]

    expected_triples_new_predicate = [[str(item) for item in triple] for triple in expected_triples_new_predicate]
    expected_triples_new_predicate.sort()

    yield pytest.param(
        original_extended,
        target_node_type,
        namespace,
        target_property,
        target_property_holding_new_property,
        expected_triples_new_predicate,
        True,
        id="Flatten with new predicate, literal to URIRef, delete intermediate node",
    )


class TestAttachPropertyFromTargetToSource:
    @pytest.mark.parametrize(
        "triples, target_node_type, namespace, "
        "target_property, target_property_holding_new_property, expected_triples, convert_literal_to_uri",
        list(generate_test_parameters_delete_target_node()),
    )
    def test_two_hop_flattener_delete_connecting_node(
        self,
        triples: list[Triple],
        target_node_type: URIRef,
        namespace: Namespace,
        target_property: URIRef,
        target_property_holding_new_property: URIRef | None,
        expected_triples: list[Triple],
        convert_literal_to_uri: bool,
    ):
        store = NeatInstanceStore.from_memory_store()

        store._add_triples(triples, named_graph=store.default_named_graph)

        transformer = AttachPropertyFromTargetToSource(
            target_node_type=target_node_type,
            target_property_holding_new_property=target_property_holding_new_property,
            target_property=target_property,
            delete_target_node=True,
            namespace=namespace,
            convert_literal_to_uri=convert_literal_to_uri,
        )

        transformer.transform(store.dataset)

        triples_after = [triple for triple in store.dataset.triples((None, None, None))]
        triples_after = [[str(item) for item in triple] for triple in triples_after]
        # Sort the triples to ensure deterministic output
        triples_after.sort()

        assert len(triples_after) == len(expected_triples)
        assert triples_after == expected_triples

    @pytest.mark.parametrize(
        "triples, target_node_type, namespace, "
        "target_property, target_property_holding_new_property, expected_triples, convert_literal_to_uri",
        list(generate_test_parameters_keep_target_node()),
    )
    def test_two_hop_flattener_keep_connecting_node(
        self,
        triples: list[Triple],
        target_node_type: URIRef,
        namespace: Namespace,
        target_property: str,
        target_property_holding_new_property: str | None,
        expected_triples: list[Triple],
        convert_literal_to_uri: bool,
    ):
        store = NeatInstanceStore.from_memory_store()

        store._add_triples(triples, named_graph=store.default_named_graph)

        transformer = AttachPropertyFromTargetToSource(
            target_node_type=target_node_type,
            namespace=namespace,
            target_property=target_property,
            target_property_holding_new_property=target_property_holding_new_property,
            delete_target_node=False,
            convert_literal_to_uri=convert_literal_to_uri,
        )

        transformer.transform(store.dataset)

        triples_after = [triple for triple in store.dataset.triples((None, None, None))]
        triples_after = [[str(item) for item in triple] for triple in triples_after]
        # Sort the triples to ensure deterministic output
        triples_after.sort()

        assert len(triples_after) == len(expected_triples)
        assert triples_after == expected_triples
