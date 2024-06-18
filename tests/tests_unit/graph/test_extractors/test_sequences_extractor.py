from cognite.client.data_classes import SequenceList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat.graph.extractors import SequencesExtractor
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_sequences_extractor():
    with monkeypatch_cognite_client() as client_mock:
        client_mock.sequences.return_value = SequenceList.load(
            (CLASSIC_CDF_EXTRACTOR_DATA / "sequences.yaml").read_text()
        )

    g = Graph()

    for triple in SequencesExtractor.from_dataset(client_mock, data_set_external_id="some data set").extract():
        g.add(triple)

    assert len(g) == 14
