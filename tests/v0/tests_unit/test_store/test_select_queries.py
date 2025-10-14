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


def test_get_graph_diff() -> None:
    """Test finding triple differences between two graphs."""
    store = NeatInstanceStore.from_oxi_local_store()
    example = Namespace("http://example.org/")

    current_graph = URIRef("urn:test:current")
    new_graph = URIRef("urn:test:new")

    # add 3 triples to current graph
    store._add_triples(
        [
            (example.subject1, example.pred1, Literal("value1")),
            (example.subject2, example.pred2, Literal("value2")),
            (example.subject3, example.pred3, Literal("value3")),
        ],
        named_graph=current_graph,
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

    # test triples to delete
    to_delete = list(store.queries.select.get_graph_diff(current_graph, new_graph))

    assert len(to_delete) == 1
    assert tuple(to_delete[0]) == (
        example.subject3,
        example.pred3,
        Literal("value3", datatype=XSD.string),
    )

    # test triples to add
    to_add = list(store.queries.select.get_graph_diff(new_graph, current_graph))

    assert len(to_add) == 1
    assert tuple(to_add[0]) == (
        example.subject4,
        example.pred4,
        Literal("value4", datatype=XSD.string),
    )
