from cognite.client.data_classes import AssetList
from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors import AssetsExtractor
from cognite.neat.graph.stores import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_asset_extractor():
    with monkeypatch_cognite_client() as client_mock:
        client_mock.assets.return_value = AssetList.load((CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml").read_text())

    store = NeatGraphStore.from_memory_store()

    extractor = AssetsExtractor.from_dataset(client_mock, data_set_external_id="nordic44")
    store.write(extractor)

    assert len(store.graph) == 73
    assert (
        len(
            list(
                store.graph.query(
                    f"Select ?s Where {{ ?s <{DEFAULT_NAMESPACE['label']}> <{DEFAULT_NAMESPACE['Label_Substation']}>}}"
                )
            )
        )
        == 1
    )
