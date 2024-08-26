import pytest
from cognite.client.data_classes import (
    AssetWrite,
    LabelDefinitionWrite,
    RelationshipWrite,
)
from rdflib import URIRef

from cognite.neat.graph.examples import nordic44_knowledge_graph
from cognite.neat.graph.extractors import RdfFileExtractor
from cognite.neat.graph.loaders import AssetLoader
from cognite.neat.graph.transformers import AddSelfReferenceProperty
from cognite.neat.issues import NeatError
from cognite.neat.issues.errors import ResourceCreationError
from cognite.neat.rules.models import AssetRules
from cognite.neat.rules.transformers import AssetToInformation
from cognite.neat.store import NeatGraphStore


@pytest.fixture()
def asset_store(asset_rules) -> NeatGraphStore:
    asset_store = NeatGraphStore.from_oxi_store()
    asset_store.write(RdfFileExtractor(nordic44_knowledge_graph, base_uri=URIRef("http://purl.org/nordic44#")))

    asset_store.add_rules(AssetToInformation().transform(asset_rules).rules)
    asset_store.transform(AddSelfReferenceProperty(rules=asset_store.rules))

    return asset_store


class TestAssetLoader:
    def test_generation_of_assets_and_relationships_no_errors(
        self, asset_rules: AssetRules, asset_store: NeatGraphStore
    ) -> None:
        loader = AssetLoader(asset_store, asset_rules, 1983, use_orphanage=True, use_labels=True)

        labels = []
        assets = []
        relationships = []
        errors = []
        for r in loader.load():
            if isinstance(r, ResourceCreationError):
                errors.append(r)
            elif isinstance(r, AssetWrite):
                assets.append(r)
            elif isinstance(r, RelationshipWrite):
                relationships.append(r)
            elif isinstance(r, LabelDefinitionWrite):
                labels.append(r)

        assert len(errors) == 0
        assert len(assets) == 631
        assert len(relationships) == 586
        assert len(labels) == 7

    def test_generation_of_assets_with_orphanage_errors(
        self, asset_rules: AssetRules, asset_store: NeatGraphStore
    ) -> None:
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
        relationships = []
        errors = []
        for r in result:
            if isinstance(r, NeatError):
                errors.append(r)
            elif isinstance(r, AssetWrite):
                assets.append(r)
            elif isinstance(r, RelationshipWrite):
                relationships.append(r)
            else:
                raise ValueError(f"Unexpected result: {r}")

        assert len(errors) == 26
        assert len(assets) == 630
        assert len(relationships) == 572
        assert assets[0] == loader.orphanage
