from cognite.client.data_classes import AssetList
from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._instances.extractors import AssetsExtractor
from cognite.neat.v0.core._store import NeatInstanceStore
from tests.v0.data import InstanceData


def test_asset_extractor_with_lambda_unpacked_metadata():
    with monkeypatch_cognite_client() as client_mock:
        assets = AssetList.load(InstanceData.AssetCentricCDF.assets_yaml.read_text())
        client_mock.assets.aggregate_count.return_value = len(assets)
        client_mock.assets.return_value = assets

    store = NeatInstanceStore.from_memory_store()

    extractor = AssetsExtractor.from_dataset(
        client_mock,
        data_set_external_id="nordic44",
        unpack_metadata=True,
    )
    store.write(extractor)

    label_id = DEFAULT_NAMESPACE["Label_Substation"]
    assert len(store.dataset) == 73
    assert len(list(store.dataset.query(f"Select ?s Where {{ ?s <{DEFAULT_NAMESPACE['labels']}> <{label_id}>}}"))) == 1
    expected_types = {"Asset"}
    actual_type = set(store.queries.select.list_types(remove_namespace=True))
    assert expected_types == actual_type


def test_asset_extractor_with_packed_metadata():
    with monkeypatch_cognite_client() as client_mock:
        assets = AssetList.load(InstanceData.AssetCentricCDF.assets_yaml.read_text())
        client_mock.assets.aggregate_count.return_value = len(assets)
        client_mock.assets.return_value = assets

    store = NeatInstanceStore.from_memory_store()

    extractor = AssetsExtractor.from_dataset(
        client_mock,
        data_set_external_id="nordic44",
        unpack_metadata=False,
    )
    store.write(extractor)

    assert len(store.dataset) == 43
    assert len(list(store.dataset.query(f"Select ?s Where {{ ?s <{DEFAULT_NAMESPACE['metadata']}> ?m}}"))) == 4
