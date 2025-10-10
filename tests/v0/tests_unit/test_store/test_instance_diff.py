import pytest
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.v0.core._constants import NAMED_GRAPH_NAMESPACE
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._store import NeatInstanceStore


def test_diff_instances() -> None:
    store = NeatInstanceStore.from_oxi_local_store()
    ex = Namespace("http://example.org/")

    current_graph = URIRef("urn:test:current")
    new_graph = URIRef("urn:test:new")

    store._add_triples(
        [
            (ex.instance1, RDF.type, ex.Type1),
            (ex.instance1, ex.prop, Literal("v1")),
            (ex.instance2, RDF.type, ex.Type1),
        ],
        named_graph=current_graph,
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

    store.diff(current_graph, new_graph)

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

    with pytest.raises(NeatValueError, match="Current named graph not found"):
        store.diff(nonexistent, existing)

    with pytest.raises(NeatValueError, match="New named graph not found"):
        store.diff(existing, nonexistent)


def test_diff_clears_previous_results() -> None:
    """Test that calling diff twice clears previous results"""
    store = NeatInstanceStore.from_oxi_local_store()
    ex = Namespace("http://example.org/")

    current1, new1 = URIRef("urn:current1"), URIRef("urn:new1")
    current2, new2 = URIRef("urn:current2"), URIRef("urn:new2")

    # First diff
    store._add_triples([(ex.a, RDF.type, ex.T1)], named_graph=current1)
    store._add_triples([(ex.b, RDF.type, ex.T1)], named_graph=new1)
    store.diff(current1, new1)

    assert (ex.b, RDF.type, ex.T1) in store.graph(NAMED_GRAPH_NAMESPACE["DIFF_ADD"])
    assert (ex.a, RDF.type, ex.T1) in store.graph(NAMED_GRAPH_NAMESPACE["DIFF_DELETE"])

    # Second diff - should clear first results
    store._add_triples([(ex.c, RDF.type, ex.T2)], named_graph=current2)
    store._add_triples([(ex.d, RDF.type, ex.T2)], named_graph=new2)
    store.diff(current2, new2)

    add_graph = store.graph(NAMED_GRAPH_NAMESPACE["DIFF_ADD"])
    delete_graph = store.graph(NAMED_GRAPH_NAMESPACE["DIFF_DELETE"])
    assert len(add_graph) == 1
    assert len(delete_graph) == 1
    assert (ex.d, RDF.type, ex.T2) in add_graph
    assert (ex.c, RDF.type, ex.T2) in delete_graph
    assert (ex.b, RDF.type, ex.T1) not in add_graph  # Cleared
    assert (ex.a, RDF.type, ex.T1) not in delete_graph  # Cleared
