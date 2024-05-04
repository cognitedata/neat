import random
from typing import Any

import pytest
from cognite.client import CogniteClient
from cognite.client.data_classes import Asset
from rdflib import Graph

from cognite.neat.legacy.graph.loaders import AssetLoader
from cognite.neat.legacy.graph.loaders.core.rdf_to_assets import categorize_assets, rdf2assets
from cognite.neat.legacy.graph.loaders.core.rdf_to_relationships import rdf2relationships
from cognite.neat.legacy.graph.stores import MemoryStore
from cognite.neat.legacy.rules.models import Rules
from tests.tests_unit.app.api.memory_cognite_client import memory_cognite_client


@pytest.fixture(scope="session")
def cognite_client():
    with memory_cognite_client() as client:
        yield client


class TestAssetLoader:
    @pytest.mark.freeze_time("2024-01-01")
    def test_vs_existing_rdf2assets(self, transformation_rules: Rules, solution_knowledge_graph: Graph):
        store = MemoryStore(solution_knowledge_graph)
        loader = AssetLoader(transformation_rules, store, data_set_id=123456, always_store_in_metadata=True)

        loaded = list(loader.load_assets(stop_on_exception=False))

        expected_assets = rdf2assets(store, transformation_rules, data_set_id=123456, stop_on_exception=False)

        # Need some extra processing to get the same format as expected_assets
        actual_dumped: dict[str, dict[str, Any]] = {}
        for asset in loaded:
            dumped = asset.dump(camel_case=False)
            if asset.labels:
                dumped["labels"] = [label.external_id for label in asset.labels]
            if "description" not in dumped:
                dumped["description"] = None
            if "parent_external_id" not in dumped:
                dumped["parent_external_id"] = None
            actual_dumped[asset.external_id] = dumped

        missing = set(expected_assets.keys()) - set(actual_dumped.keys())
        assert not missing, f"Missing {missing}"
        extra = set(actual_dumped.keys()) - set(expected_assets.keys())
        assert not extra, f"Extra {extra}"

        for external_id, expected_asset in expected_assets.items():
            # Splitting this up to get diff output
            actual_asset = actual_dumped[external_id]
            assert actual_asset == expected_asset

    @pytest.mark.freeze_time("2024-01-01")
    def test_vs_existing_rdf2relationships(self, transformation_rules: Rules, solution_knowledge_graph: Graph):
        store = MemoryStore(solution_knowledge_graph)
        loader = AssetLoader(transformation_rules, store, data_set_id=123456)

        loaded = list(loader.load_relationships(stop_on_exception=False))

        relationship_df = rdf2relationships(store, transformation_rules, data_set_id=123456, stop_on_exception=False)

        # Need some extra processing to get the same format as expected_relationships
        expected_relationships = {
            relationship["external_id"]: relationship for relationship in relationship_df.to_dict(orient="records")
        }
        actual_dumped: dict[str, dict[str, Any]] = {}
        for relationship in loaded:
            dumped = relationship.dump(camel_case=False)
            if relationship.labels:
                dumped["labels"] = [label.external_id for label in relationship.labels]
            actual_dumped[relationship.external_id] = dumped

        missing = set(expected_relationships.keys()) - set(actual_dumped.keys())
        assert not missing, f"Missing {missing}"
        extra = set(actual_dumped.keys()) - set(expected_relationships.keys())
        assert not extra, f"Extra {extra}"

    def test_categorize_assets(
        self, cognite_client: CogniteClient, transformation_rules: Rules, solution_knowledge_graph: Graph
    ) -> None:
        random.seed(42)
        store = MemoryStore(solution_knowledge_graph)
        assets = rdf2assets(store, transformation_rules, data_set_id=123456, stop_on_exception=False)
        total_assets = len(assets)
        to_modify = random.sample(list(assets.values()), int(total_assets * 0.1))
        to_update = random.sample(to_modify, int(total_assets * 0.05))
        to_update_ids = {asset["external_id"] for asset in to_update}
        to_delete = [asset for asset in to_modify if asset["external_id"] not in to_update_ids]
        to_delete_ids = {asset["external_id"] for asset in to_delete}
        new_store = {}
        for asset in to_modify:
            asset_object = Asset(**asset)
            # Need to be added.
            new_store[asset_object.external_id] = asset_object

        cognite_client.assets.store = new_store.copy()

        for asset in to_update:
            asset["description"] = "Updated description"
        assets = {external_id: asset for external_id, asset in assets.items() if external_id not in to_delete_ids}

        categorized, report = categorize_assets(cognite_client, assets, data_set_id=123456, return_report=True)

        assert len(categorized["create"]) == total_assets - len(to_modify)
        assert len(categorized["update"]) == len(to_update)
        assert len(categorized["decommission"]) == len(to_delete)

        # Reset mock store
        cognite_client.assets.store = new_store.copy()

        loader = AssetLoader(transformation_rules, store, data_set_id=123456)

        result = loader.load_to_cdf(cognite_client, output="detailed", batch_size=1000, max_retries=1, retry_delay=3)

        assert result.created == report["create"]
        assert result.updated == report["update"]
        assert result.decommissioned == report["decommission"]
        assert result.resurrected == report["resurrect"]
