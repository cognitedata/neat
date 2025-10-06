from rdflib import RDF, Literal, Namespace, URIRef
from rdflib.namespace import XSD

from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._store import NeatInstanceStore


class TestListInstanceObjectIds:
    def test_list_instance_object_ids(self) -> None:
        store = NeatInstanceStore.from_oxi_local_store()
        my_entity = DEFAULT_NAMESPACE["my_entity"]
        my_other_entity = DEFAULT_NAMESPACE["my_other_entity"]
        store._add_triples(
            [
                (my_entity, RDF.type, DEFAULT_NAMESPACE["Entity"]),
                (my_entity, DEFAULT_NAMESPACE["name"], Literal("My Entity")),
                (my_entity, DEFAULT_NAMESPACE["connection"], my_other_entity),
                (my_other_entity, RDF.type, DEFAULT_NAMESPACE["Entity"]),
            ],
            named_graph=store.default_named_graph,
        )

        result = list(store.queries.select.list_instance_object_ids())

        assert len(result) == 1
        assert result[0] == my_other_entity


def test_get_triples_to_delete() -> None:
    """Test finding triples that exist in old graph but not in new graph"""
    store = NeatInstanceStore.from_oxi_local_store()
    example = Namespace("http://example.org/")

    old_graph = URIRef("urn:test:old")
    new_graph = URIRef("urn:test:new")

    # add 3 triples to old graph
    store._add_triples(
        [
            (example.subject1, example.pred1, Literal("value1")),
            (example.subject2, example.pred2, Literal("value2")),
            (example.subject3, example.pred3, Literal("value3")),
        ],
        named_graph=old_graph,
    )

    # add 2 same triples + 1 new to new graph
    store._add_triples(
        [
            (example.subject1, example.pred1, Literal("value1")),
            (example.subject2, example.pred2, Literal("value2")),
            (example.subject4, example.pred4, Literal("value4")),
        ],
        named_graph=new_graph,
    )

    # get triples to delete
    result = list(store.queries.select.get_triples_to_delete(old_graph, new_graph))

    assert len(result) == 1
    assert tuple(result[0]) == (
        example.subject3,
        example.pred3,
        Literal("value3", datatype=XSD.string),
    )


def test_get_triples_to_add() -> None:
    """Test finding triples that exist in new graph but not in old graph"""

    store = NeatInstanceStore.from_oxi_local_store()
    example = Namespace("http://example.org/")

    old_graph = URIRef("urn:test:old")
    new_graph = URIRef("urn:test:new")

    # add 2 triples to old graph
    store._add_triples(
        [
            (example.subject1, example.pred1, Literal("value1")),
            (example.subject2, example.pred2, Literal("value2")),
        ],
        named_graph=old_graph,
    )

    # add 2 same triples + 1 new to new graph
    store._add_triples(
        [
            (example.subject1, example.pred1, Literal("value1")),
            (example.subject2, example.pred2, Literal("value2")),
            (example.subject3, example.pred3, Literal("value3")),
        ],
        named_graph=new_graph,
    )

    # get triples to add
    result = list(store.queries.select.get_triples_to_add(old_graph, new_graph))

    assert len(result) == 1
    assert tuple(result[0]) == (
        example.subject3,
        example.pred3,
        Literal("value3", datatype=XSD.string),
    )
