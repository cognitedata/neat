from typing import Iterable

import pytest
from _pytest.mark import ParameterSet
from rdflib import Namespace, URIRef, Literal

from cognite.neat._graph.transformers._prune_graph import TwoHopFlattener
from cognite.neat._store import NeatGraphStore
from cognite.neat._shared import Triple

RDF_TYPE = URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')


def generate_test_parameters() -> Iterable[ParameterSet]:
    value_property_name = "value"
    predicate_property_name = "description"
    namespace = Namespace("http://www.io-link.com/IODD/2010/10/")
    destination_node_type = namespace["TextObject"]

    triples_keep_old_predicate = [(namespace["Text-Destination-ID"],
                                   RDF_TYPE,
                                   namespace["TextObject"]),
                                  (namespace["Text-Destination-ID"],
                                   namespace["value"],
                                   Literal('Vacuum system self-check completed.')),
                                  (namespace["Device-Source-ID"],
                                   namespace["textProperty"],
                                   namespace["Text-Destination-ID"]),
                                  (namespace["Device-Source-ID"],
                                   RDF_TYPE,
                                   namespace["Device"]),
                                  ]

    expected_triples_keep_old_predicate = [(namespace["Device-Source-ID"],
                                   RDF_TYPE,
                                   namespace["Device"]),
                                  (namespace["Device-Source-ID"],
                                   namespace["textProperty"],
                                   Literal('Vacuum system self-check completed.'))
                                  ]

    expected_triples_keep_old_predicate = [[str(item) for item in triple] for triple in expected_triples_keep_old_predicate]
    expected_triples_keep_old_predicate.sort()

    yield pytest.param(triples_keep_old_predicate, destination_node_type, namespace, value_property_name, None, expected_triples_keep_old_predicate,
                       id="Flatten and keep old predicates")

    triples_new_predicate = [(namespace["Text-Destination-ID"],
                               RDF_TYPE,
                               namespace["TextObject"]),
                              (namespace["Text-Destination-ID"],
                                namespace["value"],
                               Literal('Vacuum system self-check completed.')),
                              (namespace["Text-Destination-ID"],
                               namespace["description"],
                               Literal('vacuum status')),
                              (namespace["Device-Source-ID"],
                               namespace["textProperty"],
                               namespace["Text-Destination-ID"]),
                              (namespace["Device-Source-ID"],
                               RDF_TYPE,
                               namespace["Device"]),
                              ]

    expected_triples_new_predicate = [(namespace["Device-Source-ID"],
                                       RDF_TYPE,
                                       namespace["Device"]),
                                       (namespace["Device-Source-ID"],
                                        namespace["vacuumStatus"],
                                        Literal('Vacuum system self-check completed.'))
                                       ]

    expected_triples_new_predicate = [[str(item) for item in triple] for triple in
                                       expected_triples_new_predicate]
    expected_triples_new_predicate.sort()

    yield pytest.param(triples_new_predicate, destination_node_type, namespace, value_property_name, predicate_property_name, expected_triples_new_predicate,
                       id="Flatten with new predicates")


class TestTwoHopFlattener:
    @pytest.mark.parametrize(
        "triples, destination_node_type, namespace, value_property_name, predicate_property_name, expected_triples", list(generate_test_parameters())
    )
    def test_two_hop_flattener_delete_connecting_node(
        self,
            triples: list[Triple],
            destination_node_type: URIRef,
            namespace: Namespace,
            value_property_name: str,
            predicate_property_name: str | None,
            expected_triples: list[Triple]):
        store = NeatGraphStore.from_memory_store()

        store._add_triples(triples)

        flatten_dexpi_graph = TwoHopFlattener(destination_node_type=destination_node_type,
                                               namespace=namespace,
                                               predicate_property_name=predicate_property_name,
                                               value_property_name=value_property_name,
                                               delete_connecting_node=True)


        flatten_dexpi_graph.transform(store.graph)

        triples_after = [triple for triple in store.graph.triples((None, None, None))]
        triples_after = [[str(item) for item in triple] for triple in triples_after]
        # Sort the triples to ensure deterministic output
        triples_after.sort()

        assert len(triples_after) == len(expected_triples)
        assert triples_after == expected_triples

    @pytest.mark.skip("Prepare expected triples for this test")
    @pytest.mark.parametrize(
        "triples, destination_node_type, namespace, value_property_name, predicate_property_name, expected_triples", list(generate_test_parameters())
    )
    def test_two_hop_flattener_keep_connecting_node(
        self,
            triples: list[Triple],
            destination_node_type: URIRef,
            namespace: Namespace,
            value_property_name: str,
            predicate_property_name: str | None,
            expected_triples: list[Triple]):
        store = NeatGraphStore.from_memory_store()

        store._add_triples(triples)

        flatten_dexpi_graph = TwoHopFlattener(destination_node_type=destination_node_type,
                                               namespace=namespace,
                                               predicate_property_name=predicate_property_name,
                                               value_property_name=value_property_name,
                                               delete_connecting_node=False)


        flatten_dexpi_graph.transform(store.graph)

        triples_after = [triple for triple in store.graph.triples((None, None, None))]
        triples_after = [[str(item) for item in triple] for triple in triples_after]
        # Sort the triples to ensure deterministic output
        triples_after.sort()
