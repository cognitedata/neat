from rdflib import URIRef

from cognite.neat.graph.loaders.rdf_to_dms import rdf2nodes_and_edges


# @pytest.mark.skip("Relies on a bug in the DMS exporter")
def test_rdf2nodes_and_edges(small_graph, simple_rules):
    nodes, edges, exceptions = rdf2nodes_and_edges(small_graph, simple_rules)

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

    nodes, edges, exceptions = rdf2nodes_and_edges(small_graph, simple_rules)

    assert len(nodes) == 11
    assert len(edges) == 21
    assert len(exceptions) == 1
    assert [e["type"] for e in exceptions] == ["PropertyRequiredButNotProvided"]


# @pytest.mark.skip("Relies on a bug in the DMS exporter")
def test_add_class_prefix_to_external_ids(simple_rules, graph_with_numeric_ids):
    nodes, edges, exceptions = rdf2nodes_and_edges(graph_with_numeric_ids, simple_rules, add_class_prefix=True)

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
    nodes, edges, exceptions = rdf2nodes_and_edges(graph_with_date, transformation_rules_date)

    assert exceptions == []
    assert len(nodes) == 1
    assert len(edges) == 2
    assert nodes[0].sources[0].properties["endDate"] == "2020-01-01"


def test_multi_namespace_rules(nordic44_inferred_rules, source_knowledge_graph):
    source_knowledge_graph.graph.bind(
        nordic44_inferred_rules.metadata.prefix, nordic44_inferred_rules.metadata.namespace
    )
    nodes, _, _ = rdf2nodes_and_edges(source_knowledge_graph, nordic44_inferred_rules, add_class_prefix=True)

    assert len(nodes) == 493
