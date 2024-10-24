from cognite.client.data_classes import SequenceList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat._graph.extractors import SequencesExtractor
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_sequences_extractor():
    with monkeypatch_cognite_client() as client_mock:
        sequences = SequenceList.load((CLASSIC_CDF_EXTRACTOR_DATA / "sequences.yaml").read_text())
        client_mock.sequences.return_value = sequences
        client_mock.sequences.aggregate_count.return_value = len(sequences)

    g = Graph()

    for triple in SequencesExtractor.from_dataset(client_mock, data_set_external_id="some data set").extract():
        g.add(triple)

    assert len(g) == 14
