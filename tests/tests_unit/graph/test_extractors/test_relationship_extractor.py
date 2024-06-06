from cognite.client.data_classes import RelationshipList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat.graph.extractors import RelationshipsExtractor
from tests.tests_unit.graph.test_extractors.constants import RELATIONSHIP_EXTRACTOR_DATA


def test_asset_extractor():
    with monkeypatch_cognite_client() as client_mock:
        client_mock.relationships.return_value = RelationshipList.load(
            (RELATIONSHIP_EXTRACTOR_DATA / "nordic44_relationships.yaml").read_text()
        )

    g = Graph()

    for triple in RelationshipsExtractor.from_dataset(client_mock, data_set_external_id="nordic44").extract():
        g.add(triple)

    assert len(g) == 14976
