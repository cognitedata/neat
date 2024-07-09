from cognite.client.data_classes import AssetList
from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors import AssetsExtractor
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.utils.utils import create_sha256_hash
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_asset_extractor():
    with monkeypatch_cognite_client() as client_mock:
        assets = AssetList.load((CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml").read_text())
        client_mock.assets.aggregate_count.return_value = len(assets)
        client_mock.assets.return_value = assets

    store = NeatGraphStore.from_memory_store()

    extractor = AssetsExtractor.from_dataset(
        client_mock, data_set_external_id="nordic44", to_type=lambda a: a.metadata.get("type", "Unknown")
    )
    store.write(extractor)

    label_id = DEFAULT_NAMESPACE[f'Label_{create_sha256_hash("Substation")}']
    assert len(store.graph) == 73
    assert len(list(store.graph.query(f"Select ?s Where {{ ?s <{DEFAULT_NAMESPACE['label']}> <{label_id}>}}"))) == 1
    expected_types = {"Substation", "SubGeographicalRegion", "GeographicalRegion", "RootCIMNode"}
    actual_type = set(store.queries.list_types(remove_namespace=True))
    assert expected_types == actual_type
