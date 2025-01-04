from unittest.mock import MagicMock

from cognite.client._api.sequences import SequencesAPI, SequencesDataAPI
from cognite.client.data_classes import SequenceList, SequenceRowsList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat._graph.extractors import SequencesExtractor
from cognite.neat._utils.rdf_ import remove_namespace_from_uri
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_sequences_extractor():
    row_list = SequenceRowsList.load((CLASSIC_CDF_EXTRACTOR_DATA / "sequence_rows.yaml").read_text())
    rows_by_id = {row.id: row for row in row_list}

    def mock_row_retrieve(id: list[int]) -> SequenceRowsList:
        return SequenceRowsList([rows_by_id[i] for i in id])

    with monkeypatch_cognite_client() as client_mock:
        sequences = SequenceList.load((CLASSIC_CDF_EXTRACTOR_DATA / "sequences.yaml").read_text())
        # Bug in SDK, sequences is mocked incorrectly
        client_mock.sequences = MagicMock(spec=SequencesAPI)
        client_mock.sequences.rows = MagicMock(spec_set=SequencesDataAPI)

        client_mock.config.max_workers = 10
        client_mock.sequences.return_value = sequences
        client_mock.sequences.aggregate_count.return_value = len(sequences)
        client_mock.sequences.rows.retrieve.side_effect = mock_row_retrieve

    g = Graph()

    for triple in SequencesExtractor.from_dataset(
        client_mock, data_set_external_id="some data set", as_write=False
    ).extract():
        g.add(triple)

    assert len(g) == 26
    assert unique_properties(g) == {
        "assetId",
        "columns",
        "rows",
        "dataSetId",
        "createdTime",
        "lastUpdatedTime",
        "name",
        "externalId",
        "type",
    }


def unique_properties(g: Graph) -> set[str]:
    result = g.query("""
    select distinct ?predicate
    where {
        ?subject ?predicate ?object
    }
    """)

    return {remove_namespace_from_uri(row[0]) for row in result}
