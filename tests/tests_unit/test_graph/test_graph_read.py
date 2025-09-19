from cognite.client.data_classes import AssetList
from cognite.client.testing import monkeypatch_cognite_client

from tests.data import InstanceData
from thisisneat.core._constants import DEFAULT_NAMESPACE
from thisisneat.core._instances.extractors import AssetsExtractor
from thisisneat.core._store import NeatInstanceStore


def test_asset_extractor():
    with monkeypatch_cognite_client() as client_mock:
        assets = AssetList.load(InstanceData.AssetCentricCDF.assets_yaml.read_text())
        client_mock.assets.aggregate_count.return_value = len(assets)
        client_mock.assets.return_value = assets

    store = NeatInstanceStore.from_memory_store()

    extractor = AssetsExtractor.from_dataset(client_mock, data_set_external_id="nordic44", unpack_metadata=True)
    store.write(extractor)

    assert len([instance for instance in store.read(DEFAULT_NAMESPACE.Asset)]) == 4
    assert len(store.dataset) == 73
