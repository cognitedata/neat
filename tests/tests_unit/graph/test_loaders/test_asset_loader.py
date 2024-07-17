from rdflib import URIRef

from cognite.neat.graph.examples import nordic44_knowledge_graph
from cognite.neat.graph.extractors import RdfFileExtractor
from cognite.neat.graph.issues.loader import InvalidInstanceError
from cognite.neat.graph.loaders import AssetLoader
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.graph.transformers import AddAllReferences


def test_generation_of_assets(asset_rules):
    asset_store = NeatGraphStore.from_memory_store()
    asset_store.write(RdfFileExtractor(nordic44_knowledge_graph, base_uri=URIRef("http://purl.org/nordic44#")))

    asset_store.add_rules(asset_rules.as_information_rules())
    asset_store.transform(AddAllReferences(rules=asset_store.rules))

    loader = AssetLoader(asset_store, asset_rules, 1983)
    result = list(loader._load())

    assets = []
    errors = []
    for r in result:
        if not isinstance(r, InvalidInstanceError):
            assets.append(r)
        else:
            errors.append(r)

    assert len(errors) == 0
    assert len(assets) == 452
