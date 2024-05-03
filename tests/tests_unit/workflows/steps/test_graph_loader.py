from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cognite.client.data_classes import Asset, AssetList, Label
from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat.app.monitoring.metrics import NeatMetricsCollector
from cognite.neat.config import Config
from cognite.neat.legacy.graph.stores import MemoryStore
from cognite.neat.legacy.rules.exporters._core.rules2labels import get_labels
from cognite.neat.workflows.steps.data_contracts import RulesData, SolutionGraph
from cognite.neat.workflows.steps.lib.v1.graph_loader import GenerateAssetsFromGraph


@pytest.fixture
def config_mock() -> Config:
    mock = MagicMock(spec=Config)
    mock.data_store_path = Path("/app/data")
    return mock


def test_graph_loader_clean_orphans(
    solution_knowledge_graph_dirty, transformation_rules, mock_cdf_assets, config_mock: Config
):
    with monkeypatch_cognite_client() as client_mock:

        def list_assets(data_set_ids: int = 123456, limit: int = -1, labels=None, **_):
            return AssetList([Asset(**asset) for asset in mock_cdf_assets.values()])

        def list_labels(**_):
            label_names = [*list(get_labels(transformation_rules)), "non-historic", "historic"]
            return [Label(external_id=label_name, name=label_names) for label_name in label_names]

        client_mock.assets.list = list_assets
        client_mock.labels.list = list_labels

    rules = RulesData(rules=transformation_rules)
    solution_graph = SolutionGraph(
        graph=MemoryStore(
            graph=solution_knowledge_graph_dirty,
            namespace="http://purl.org/cognite/tnt#",
            prefixes=solution_knowledge_graph_dirty.namespaces,
        )
    )
    test_assets_from_graph = GenerateAssetsFromGraph(config_mock)
    test_assets_from_graph.configs = {"assets_cleanup_type": "orphans", "data_set_id": 123456}
    test_assets_from_graph.metrics = NeatMetricsCollector("TestMetrics")

    _, assets = test_assets_from_graph.run(rules=rules, cdf_client=client_mock, solution_graph=solution_graph)

    assets_external_ids = [asset.external_id for asset in assets.assets["create"]]
    assert "2dd90176-bdfb-11e5-94fa-c8f73332c8f4-terminal-orphan-test" not in assets_external_ids
    assert "f17695fe-9aeb-11e5-91da-b8763fd99c5f-orphan-test" not in assets_external_ids
    assert "f17695fe-9aeb-11e5-91da-b8763fd99c5f" not in assets_external_ids
    assert "2dd90176-bdfb-11e5-94fa-c8f73332c8f4" not in assets_external_ids
    assert "root-node" in assets_external_ids


def test_graph_loader_no_orphans_cleanup(
    solution_knowledge_graph_dirty, transformation_rules, mock_cdf_assets, config_mock: Config
):
    with monkeypatch_cognite_client() as client_mock:

        def list_assets(data_set_ids: int = 123456, limit: int = -1, labels=None, **_):
            return AssetList([Asset(**asset) for asset in mock_cdf_assets.values()])

        def list_labels(**_):
            label_names = [*list(get_labels(transformation_rules)), "non-historic", "historic"]
            return [Label(external_id=label_name, name=label_names) for label_name in label_names]

        client_mock.assets.list = list_assets
        client_mock.labels.list = list_labels

    rules = RulesData(rules=transformation_rules)
    solution_graph = SolutionGraph(
        graph=MemoryStore(
            graph=solution_knowledge_graph_dirty,
            namespace="http://purl.org/cognite/tnt#",
            prefixes=solution_knowledge_graph_dirty.namespaces,
        )
    )
    test_assets_from_graph = GenerateAssetsFromGraph(config_mock)
    test_assets_from_graph.configs = {"assets_cleanup_type": "nothing", "data_set_id": 123456}
    test_assets_from_graph.metrics = NeatMetricsCollector("TestMetrics")

    _, assets = test_assets_from_graph.run(rules=rules, cdf_client=client_mock, solution_graph=solution_graph)

    assets_external_ids = [asset.external_id for asset in assets.assets["create"]]
    assert "2dd90176-bdfb-11e5-94fa-c8f73332c8f4-terminal-orphan-test" in assets_external_ids
    assert "f17695fe-9aeb-11e5-91da-b8763fd99c5f-orphan-test" in assets_external_ids
    assert "f17695fe-9aeb-11e5-91da-b8763fd99c5f" in assets_external_ids
    assert "2dd90176-bdfb-11e5-94fa-c8f73332c8f4" in assets_external_ids
    assert "orphanage" in assets_external_ids
