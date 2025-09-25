from cognite.client.data_classes import FileMetadataList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat.v0.core._instances.extractors import FilesExtractor
from tests.v0.data import InstanceData


def test_timeseries_extractor():
    with monkeypatch_cognite_client() as client_mock:
        client_mock.files.return_value = FileMetadataList.load(InstanceData.AssetCentricCDF.files_yaml.read_text())

    g = Graph()

    for triple in FilesExtractor.from_dataset(client_mock, data_set_external_id="some data set").extract():
        g.add(triple)

    assert len(g) == 13
