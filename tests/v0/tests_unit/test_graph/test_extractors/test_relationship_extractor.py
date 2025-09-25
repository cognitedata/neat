from cognite.client.data_classes import RelationshipList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat.v0.core._instances.extractors import RelationshipsExtractor
from tests.v0.data import InstanceData


def test_asset_extractor():
    with monkeypatch_cognite_client() as client_mock:
        client_mock.relationships.return_value = RelationshipList.load(
            InstanceData.AssetCentricCDF.relationships_yaml.read_text()
        )

    g = Graph()

    for triple in RelationshipsExtractor.from_dataset(
        client_mock, data_set_external_id="some data set", identifier="externalId"
    ).extract():
        g.add(triple)

    assert len(g) == 44
