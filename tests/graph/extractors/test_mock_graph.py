from cognite.neat.graph import extractors, loaders
from cognite.neat.graph.loaders.core import rdf_to_relationships
from cognite.neat.graph.stores import MemoryStore
from cognite.neat.rules.models.rules import Rules
from cognite.neat.utils.utils import remove_namespace


def test_mock_graph(transformation_rules: Rules):
    rules = transformation_rules

    class_count = {
        "RootCIMNode": 1,
        "GeographicalRegion": 5,
        "SubGeographicalRegion": 10,
        "Substation": 20,
        "Terminal": 60,
    }

    graph_store = MemoryStore(prefixes=rules.prefixes, namespace=rules.metadata.namespace)
    graph_store.init_graph(base_prefix=rules.metadata.prefix)

    mock_triples = extractors.MockGraphGenerator(rules, class_count).extract()
    graph_store.add_triples(mock_triples)

    graph_class_count = {
        remove_namespace(res[0]): int(res[1])
        for res in list(
            graph_store.graph.query(
                "SELECT ?class (count(?s) as ?instances ) "
                "WHERE { ?s a ?class . } group by ?class "
                "order by DESC(?instances)"
            )
        )
    }

    assets = loaders.rdf2assets(graph_store, rules, data_set_id=123456)
    relationships = rdf_to_relationships.rdf2relationships(graph_store, rules, data_set_id=123456)

    assert len(mock_triples) == 503
    assert len(assets) == 97
    assert graph_class_count == class_count
    assert len(relationships) == 135
