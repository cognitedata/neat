from cognite.neat.core import loaders, loader
from cognite.neat.core.loaders.cdfcore import rdf_to_relationships
from cognite.neat.core.mocks.graph import generate_triples
from cognite.neat.core.rules.models import TransformationRules
from cognite.neat.core.utils.utils import add_triples, remove_namespace


def test_mock_graph(transformation_rules: TransformationRules):
    rules = transformation_rules

    class_count = {
        "RootCIMNode": 1,
        "GeographicalRegion": 5,
        "SubGeographicalRegion": 10,
        "Substation": 20,
        "Terminal": 60,
    }

    graph_store = loader.NeatGraphStore(prefixes=rules.prefixes, namespace=rules.metadata.namespace)
    graph_store.init_graph(base_prefix=rules.metadata.prefix)

    mock_triples = generate_triples(rules, class_count)
    add_triples(graph_store, mock_triples)

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

    assets = loaders.rdf2assets(graph_store, rules)
    relationships = rdf_to_relationships.rdf2relationships(graph_store, rules)

    assert len(mock_triples) == 503
    assert len(assets) == 97
    assert graph_class_count == class_count
    assert len(relationships) == 135
