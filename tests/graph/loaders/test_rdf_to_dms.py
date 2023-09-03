from rdflib import URIRef

from cognite.neat.graph.loaders.rdf_to_dms import rdf2nodes_and_edges


def test_rdf2nodes_and_edges(small_graph, simple_rules):
    nodes, edges, exceptions = rdf2nodes_and_edges(small_graph, simple_rules)

    assert exceptions == []
    assert len(nodes) == 13
    assert len(edges) == 24


def test_rdf2nodes_and_edges_raise_exception(small_graph, simple_rules):
    small_graph.graph.remove(
        (URIRef("http://purl.org/cognite/neat#Nordics"), URIRef("http://purl.org/cognite/neat#name"), None)
    )

    small_graph.graph.remove(
        (URIRef("http://purl.org/cognite/neat#Nordics.Norway.NO1"), URIRef("http://purl.org/cognite/neat#name"), None)
    )

    nodes, edges, exceptions = rdf2nodes_and_edges(small_graph, simple_rules)

    assert len(exceptions) == 2
    assert len(nodes) == 11
    assert len(edges) == 21
    assert [e["type"] for e in exceptions] == ["MissingInstanceTriples", "PropertyRequiredButNotProvided"]
