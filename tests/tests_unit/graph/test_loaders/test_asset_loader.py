import pytest
from rdflib import URIRef

from cognite.neat.graph.examples import nordic44_knowledge_graph
from cognite.neat.graph.extractors import RdfFileExtractor
from cognite.neat.graph.issues.loader import InvalidInstanceError
from cognite.neat.graph.loaders import AssetLoader
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.graph.transformers import AddSelfReferenceProperty
from cognite.neat.rules.models.asset._rules import AssetClass
from cognite.neat.rules.models.entities import AssetEntity, ClassEntity


@pytest.fixture()
def asset_store(asset_rules) -> NeatGraphStore:
    asset_store = NeatGraphStore.from_memory_store()
    asset_store.write(RdfFileExtractor(nordic44_knowledge_graph, base_uri=URIRef("http://purl.org/nordic44#")))

    asset_store.add_rules(asset_rules.as_information_rules())
    asset_store.transform(AddSelfReferenceProperty(rules=asset_store.rules))

    return asset_store


class TestAssetLoader:
    def test_generation_of_assets_no_errors(self, asset_rules, asset_store):
        loader = AssetLoader(asset_store, asset_rules, 1983)
        result = list(loader.load())

        assets = []
        errors = []
        for r in result:
            if not isinstance(r, InvalidInstanceError):
                assets.append(r)
            else:
                errors.append(r)

        assert len(errors) == 0
        assert len(assets) == 452

    def test_generation_of_assets_with_orphanage_errors(self, asset_rules, asset_store):
        asset_rules = asset_rules.model_copy(deep=True)

        # a bit nasty update of rules to produce errors and orphanage
        asset_rules.properties.data[0].transformation = asset_store.rules.properties.data[0].transformation
        asset_rules.properties.data[1].transformation = asset_store.rules.properties.data[1].transformation
        asset_rules.properties.data[3].value_type = ClassEntity(prefix="cim", suffix="ConnectivityNode")
        asset_rules.properties.data[3].implementation = [AssetEntity(property="parentExternalId")]
        asset_rules.classes.data += [AssetClass(class_=ClassEntity(prefix="cim", suffix="ConnectivityNode"))]

        asset_store.add_rules(asset_rules.as_information_rules())

        loader = AssetLoader(asset_store, asset_rules, 1983, use_orphanage=True)
        result = list(loader.load())

        assets = []
        errors = []
        for r in result:
            if not isinstance(r, InvalidInstanceError):
                assets.append(r)
            else:
                errors.append(r)

        assert len(errors) == 541
        assert len(assets) == 453
        assert assets[0] == loader.orphanage
        assert assets[1].parent_external_id == assets[0].external_id
