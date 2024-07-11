from cognite.client.data_classes import AssetList
from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat.graph.extractors import AssetsExtractor
from cognite.neat.graph.loaders import DMSLoader
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.rules.importers import InferenceImporter
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_asset_extractor_with_packed_metadata():
    with monkeypatch_cognite_client() as client_mock:
        assets = AssetList.load((CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml").read_text())
        client_mock.assets.aggregate_count.return_value = len(assets)
        client_mock.assets.return_value = assets

    store = NeatGraphStore.from_memory_store()
    store.write(AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml", unpack_metadata=False))

    importer = InferenceImporter.from_graph_store(store, check_for_json_string=True, prefix="some-prefix")

    rules, _ = importer.to_rules()
    store.add_rules(rules)

    dms_rules = rules.as_dms_architect_rules()

    loader = DMSLoader.from_rules(dms_rules, store, dms_rules.metadata.space)
    instances = {instance.external_id: instance for instance in loader._load()}

    assert isinstance(instances["Asset_4288662884680989"].sources[0].properties["metadata"], dict)
