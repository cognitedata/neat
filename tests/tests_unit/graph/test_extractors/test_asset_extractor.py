from cognite.client.data_classes import AssetList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors import AssetsExtractor
from tests.tests_unit.graph.test_extractors.constants import ASSET_EXTRACTOR_DATA


def test_asset_extractor():
    with monkeypatch_cognite_client() as client_mock:
        client_mock.assets.return_value = AssetList.load((ASSET_EXTRACTOR_DATA / "nordic44_assets.yaml").read_text())

    g = Graph()

    for triple in AssetsExtractor.from_dataset(client_mock, data_set_external_id="nordic44").extract():
        g.add(triple)

    assert len(g) == 18675
    assert len(list(g.query(f"Select ?s Where {{ ?s <{DEFAULT_NAMESPACE['label']}> 'Substation'}}"))) == 44
