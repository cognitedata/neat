from cognite.client.data_classes import AssetList
from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat.graph.extractors import AssetsExtractor
from cognite.neat.rules.importers import InferenceImporter
from cognite.neat.stores import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_asset_extractor():
    with monkeypatch_cognite_client() as client_mock:
        assets = AssetList.load((CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml").read_text())
        client_mock.assets.aggregate_count.return_value = len(assets)
        client_mock.assets.return_value = assets

    store = NeatGraphStore.from_memory_store()

    extractor = AssetsExtractor.from_dataset(client_mock, data_set_external_id="nordic44", unpack_metadata=True)
    store.write(extractor)

    rules, _ = InferenceImporter.from_graph_store(store).to_rules()
    store.add_rules(rules)

    assert len([instance for instance in store.read("Asset")]) == 4
    assert len(store.graph) == 73
