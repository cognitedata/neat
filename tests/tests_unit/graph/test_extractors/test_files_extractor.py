from cognite.client.data_classes import FileMetadataList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat.graph.extractors import FilesExtractor
from tests.tests_unit.graph.test_extractors.constants import FILES_EXTRACTOR_DATA


def test_timeseries_extractor():
    with monkeypatch_cognite_client() as client_mock:
        client_mock.files.return_value = FileMetadataList.load(
            (FILES_EXTRACTOR_DATA / "dtu_metmast_files.yaml").read_text()
        )

    g = Graph()

    for triple in FilesExtractor.from_dataset(client_mock, data_set_external_id="dtu_met_mast").extract():
        g.add(triple)

    assert len(g) == 90
