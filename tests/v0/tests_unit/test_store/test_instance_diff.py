import pytest
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.v0.core._constants import NAMED_GRAPH_NAMESPACE
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._store import NeatInstanceStore


def test_diff_instances() -> None:
    store = NeatInstanceStore.from_oxi_local_store()
    ex = Namespace("http://example.org/")

    old_graph = URIRef("urn:test:old")
    new_graph = URIRef("urn:test:new")

    store._add_triples(
        [
            (ex.instance1, RDF.type, ex.Type1),
            (ex.instance1, ex.prop, Literal("v1")),
            (ex.instance2, RDF.type, ex.Type1),
        ],
        named_graph=old_graph,
    )

    # NEW: 1 modified + 1 new (instance2 deleted)
    store._add_triples(
        [
            (ex.instance1, RDF.type, ex.Type1),
            (ex.instance1, ex.prop, Literal("v1_modified")),
            (ex.instance3, RDF.type, ex.Type2),
        ],
        named_graph=new_graph,
    )

    store.diff(old_graph, new_graph)

    add_graph = store.graph(NAMED_GRAPH_NAMESPACE["DIFF_ADD"])
    delete_graph = store.graph(NAMED_GRAPH_NAMESPACE["DIFF_DELETE"])
    assert (ex.instance3, RDF.type, ex.Type2) in add_graph
    assert (ex.instance1, ex.prop, Literal("v1_modified")) in add_graph
    assert (ex.instance2, RDF.type, ex.Type1) in delete_graph
    assert (ex.instance1, ex.prop, Literal("v1")) in delete_graph


def test_diff_validation() -> None:
    store = NeatInstanceStore.from_oxi_local_store()

    existing = URIRef("urn:test:exists")
    nonexistent = URIRef("urn:test:nonexistent")

    store._add_triples(
        [
            (URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/T")),
        ],
        named_graph=existing,
    )

    with pytest.raises(NeatValueError, match="Old named graph not found"):
        store.diff(nonexistent, existing)

    with pytest.raises(NeatValueError, match="New named graph not found"):
        store.diff(existing, nonexistent)
