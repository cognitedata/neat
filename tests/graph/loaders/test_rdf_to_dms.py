from rdflib import URIRef

from cognite.neat.graph import loaders


def test_rdf2nodes_and_edges(small_graph, simple_rules):
    loader = loaders.DMSLoader(simple_rules, small_graph)
    nodes, edges, exceptions = loader.as_nodes_and_edges()

    assert exceptions == []
    assert len(nodes) == 13
    assert len(edges) == 24


# @pytest.mark.skip("Relies on a bug in the DMS exporter")
def test_rdf2nodes_and_edges_raise_exception(small_graph, simple_rules):
    small_graph.graph.remove(
        (URIRef("http://purl.org/cognite/neat#Nordics"), URIRef("http://purl.org/cognite/neat#name"), None)
    )

    # this will basically remove instance all together since there are no triples
    # left to define this instance
    small_graph.graph.remove(
        (URIRef("http://purl.org/cognite/neat#Nordics.Norway.NO1"), URIRef("http://purl.org/cognite/neat#name"), None)
    )

    loader = loaders.DMSLoader(simple_rules, small_graph)
    nodes, edges, exceptions = loader.as_nodes_and_edges()

    assert len(nodes) == 11
    assert len(edges) == 21
    assert len(exceptions) == 1
    assert [e["type"] for e in exceptions] == ["PropertyRequiredButNotProvided"]


# @pytest.mark.skip("Relies on a bug in the DMS exporter")
def test_add_class_prefix_to_external_ids(simple_rules, graph_with_numeric_ids):
    loader = loaders.DMSLoader(simple_rules, graph_with_numeric_ids, add_class_prefix=True)
    nodes, edges, exceptions = loader.as_nodes_and_edges()

    # Needs this as order of end nodes is not guaranteed
    start_node_xid = set()
    end_node_xid = set()
    for edge in edges:
        start_node_xid.add(edge.start_node.external_id)
        end_node_xid.add(edge.end_node.external_id)

    assert exceptions == []
    assert len(nodes) == 1
    assert len(edges) == 2
    assert nodes[0].external_id == "PriceAreaConnection_1"
    assert start_node_xid == {"PriceAreaConnection_1"}
    assert end_node_xid == {"PriceArea_2", "PriceArea_3"}


# @pytest.mark.skip("Relies on a bug in the DMS exporter")
def test_rdf2nodes_property_date(graph_with_date, transformation_rules_date):
    loader = loaders.DMSLoader(transformation_rules_date, graph_with_date)
    nodes, edges, exceptions = loader.as_nodes_and_edges()

    assert exceptions == []
    assert len(nodes) == 1
    assert len(edges) == 2
    assert nodes[0].sources[0].properties["endDate"] == "2020-01-01"


def test_multi_namespace_rules(nordic44_inferred_rules, source_knowledge_graph):
    source_knowledge_graph.graph.bind(
        nordic44_inferred_rules.metadata.prefix, nordic44_inferred_rules.metadata.namespace
    )
    loader = loaders.DMSLoader(nordic44_inferred_rules, source_knowledge_graph, add_class_prefix=True)
    nodes, _, _ = loader.as_nodes_and_edges()

    assert len(nodes) == 493
