import yaml
from cognite.client.data_classes import AssetList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import URIRef

from cognite.neat.graph.extractors._asset import AssetExtractor
from tests.tests_unit.graph.test_extractors.constants import ASSET_EXTRACTOR_DATA


def test_asset_extractor():
    with monkeypatch_cognite_client() as client_mock:

        def list_assets(**_):
            return AssetList.load(yaml.safe_load((ASSET_EXTRACTOR_DATA / "nordic44_assets.yaml").read_text()))

        client_mock.assets.list = list_assets

    triples = AssetExtractor(client_mock).extract()

    assert len(triples) == 18675
    assert sum(1 for t in triples if t[2] == URIRef("http://purl.org/cognite/neat#Substation")) == 44
