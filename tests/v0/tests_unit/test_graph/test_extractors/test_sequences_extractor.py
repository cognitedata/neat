import pytest
from cognite.client import CogniteClient
from cognite.client.data_classes import SequenceList, SequenceRowsList
from cognite.client.exceptions import CogniteAPIError
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat.v0.core._instances.extractors import SequencesExtractor
from cognite.neat.v0.core._issues import catch_warnings
from cognite.neat.v0.core._issues.warnings import CDFAuthWarning
from cognite.neat.v0.core._utils.rdf_ import Triple, remove_namespace_from_uri
from tests.v0.data import InstanceData


@pytest.fixture
def client_mock() -> CogniteClient:
    row_list = SequenceRowsList.load(InstanceData.AssetCentricCDF.sequence_rows_yaml.read_text())
    rows_by_id = {row.id: row for row in row_list}

    def mock_row_retrieve(id: list[int]) -> SequenceRowsList:
        return SequenceRowsList([rows_by_id[i] for i in id])

    with monkeypatch_cognite_client() as client_mock:
        sequences = SequenceList.load(InstanceData.AssetCentricCDF.sequences_yaml.read_text())
        client_mock.config.max_workers = 10
        client_mock.sequences.return_value = sequences
        client_mock.sequences.aggregate_count.return_value = len(sequences)
        client_mock.sequences.rows.retrieve.side_effect = mock_row_retrieve
        yield client_mock


def test_sequences_extractor(client_mock: CogniteClient) -> None:
    g = Graph()
    for triple in SequencesExtractor.from_dataset(
        client_mock, data_set_external_id="some data set", as_write=True
    ).extract():
        g.add(triple)

    assert unique_properties(g) == {
        "assetId",
        "columns",
        "rows",
        "dataSetId",
        "name",
        "externalId",
        "type",
    }
    assert len(g) == 22


def test_sequence_extractor_unpack_columns(client_mock: CogniteClient) -> None:
    g = Graph()
    for triple in SequencesExtractor.from_dataset(
        client_mock, data_set_external_id="some data set", as_write=True, unpack_columns=True
    ).extract():
        g.add(triple)

    assert unique_properties(g) == {
        "assetId",
        "dataSetId",
        "name",
        "externalId",
        "type",
        "0Values",
        "1Values",
        "2Values",
        "3Values",
        "0",
        "1",
        "2",
        "3",
        "columnOrder",
        "columnValueTypes",
    }
    assert len(g) == 34


def unique_properties(g: Graph) -> set[str]:
    result = g.query("""
    select distinct ?predicate
    where {
        ?subject ?predicate ?object
    }
    """)

    return {remove_namespace_from_uri(row[0]) for row in result}


def test_no_access() -> None:
    def raise_exception(*args, **kwargs):
        raise CogniteAPIError(
            code=403,
            x_request_id="",
            message="Not allowed to read sequences",
        )

    with monkeypatch_cognite_client() as client_mock:
        client_mock.sequences.aggregate_count.side_effect = raise_exception

        triples: list[Triple] = []
        with catch_warnings() as issue_list:
            extractor = SequencesExtractor.from_hierarchy(client_mock, root_asset_external_id="root")
            for triple in extractor.extract():
                triples.append(triple)

        assert len(triples) == 0
        assert len(issue_list) == 1
        issue = issue_list[0]
        assert isinstance(issue, CDFAuthWarning)
