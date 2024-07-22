import pytest
from rdflib import URIRef

from cognite.neat.graph.examples import nordic44_knowledge_graph
from cognite.neat.graph.extractors import RdfFileExtractor
from cognite.neat.graph.issues.loader import InvalidInstanceError
from cognite.neat.graph.loaders import AssetLoader
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.graph.transformers import AddSelfReferenceProperty


@pytest.fixture()
def asset_store(asset_rules) -> NeatGraphStore:
    asset_store = NeatGraphStore.from_memory_store()
    asset_store.write(RdfFileExtractor(nordic44_knowledge_graph, base_uri=URIRef("http://purl.org/nordic44#")))

    asset_store.add_rules(asset_rules.as_information_rules())
    asset_store.transform(AddSelfReferenceProperty(rules=asset_store.rules))

    return asset_store


class TestAssetLoader:
    def test_generation_of_assets_no_errors(self, asset_rules, asset_store):
        loader = AssetLoader(asset_store, asset_rules, 1983, use_orphanage=True)
        result = list(loader.load())

        assets = []
        errors = []
        for r in result:
            if not isinstance(r, InvalidInstanceError):
                assets.append(r)
            else:
                errors.append(r)

        assert len(errors) == 0
        assert len(assets) == 631

    def test_generation_of_assets_with_orphanage_errors(self, asset_rules, asset_store):
        asset_store.graph.remove(
            (
                URIRef("http://purl.org/nordic44#_f17695a9-9aeb-11e5-91da-b8763fd99c5f"),
                None,
                None,
            )
        )
        loader = AssetLoader(asset_store, asset_rules, 1983, use_orphanage=True)
        result = list(loader.load())

        assets = []
        errors = []
        for r in result:
            if not isinstance(r, InvalidInstanceError):
                assets.append(r)
            else:
                errors.append(r)

        assert len(errors) == 13
        assert len(assets) == 630
        assert assets[0] == loader.orphanage
