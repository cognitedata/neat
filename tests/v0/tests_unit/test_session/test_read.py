from cognite.client.data_classes import FileMetadataList, TimeSeriesList
from cognite.client.data_classes.data_modeling import NodeId

from cognite.neat import NeatSession
from cognite.neat.v0.core._client.testing import monkeypatch_neat_client
from cognite.neat.v0.core._constants import CLASSIC_CDF_NAMESPACE, NAMED_GRAPH_NAMESPACE
from cognite.neat.v0.core._instances.extractors._classic_cdf._base import InstanceIdPrefix
from cognite.neat.v0.core._issues import NeatIssue
from cognite.neat.v0.core._issues.warnings import NeatValueWarning
from tests.v0.data import InstanceData


class TestReadClassicTimeSeries:
    def test_read_times_series(self) -> None:
        with monkeypatch_neat_client() as client:
            timeseries = TimeSeriesList.load(InstanceData.AssetCentricCDF.timeseries_yaml.read_text(encoding="utf-8"))
            assert len(timeseries) >= 2
            # TimeSeries with InstanceId should be skipped
            timeseries[0].instance_id = NodeId("already", "connected")
            # The timeseries with instance_id should be skipped
            expected_connection_drop = sum(1 for ts in timeseries if ts.asset_id) - 1
            client.time_series.aggregate_count.return_value = len(timeseries)
            client.time_series.return_value = timeseries

            neat: NeatSession = NeatSession(client)

        issues = neat.read.cdf.classic.time_series("my_data_set", identifier="externalId")
        dropped_connections: list[NeatValueWarning] = []
        unexpected_issues: list[NeatIssue] = []
        for issue in issues:
            if isinstance(issue, NeatValueWarning) and issue.value.startswith("Skipping connection"):
                dropped_connections.append(issue)
            else:
                unexpected_issues.append(issue)
        assert not unexpected_issues
        assert len(dropped_connections) == expected_connection_drop

        instances_ids = sorted((id_ for id_, _ in neat._state.instances.store.queries.select.list_instances_ids()))

        expected = sorted(
            [
                CLASSIC_CDF_NAMESPACE[f"{InstanceIdPrefix.time_series}{ts.external_id}"]
                for ts in timeseries
                if ts.instance_id is None
            ]
        )
        assert instances_ids == expected

        for instance_id in instances_ids:
            _, properties = neat._state.instances.store.queries.select.describe(instance_id)
            assert "isString" in properties
            value = properties["isString"][0]
            assert isinstance(value, str), f"The {instance_id} has not converted the isSting from bool to enum"

    def test_read_file_metadata(self) -> None:
        with monkeypatch_neat_client() as client:
            file_metadata = FileMetadataList.load(InstanceData.AssetCentricCDF.files_yaml.read_text(encoding="utf-8"))
            assert len(file_metadata) >= 2
            # FileMetadata with InstanceId should be skipped
            file_metadata[0].instance_id = NodeId("already", "connected")
            expected_connection_drop = sum(
                1 for fm in file_metadata for _ in fm.asset_ids or [] if fm.instance_id is None
            )
            client.files.return_value = file_metadata

            neat: NeatSession = NeatSession(client)

        issues = neat.read.cdf.classic.file_metadata("my_data_set", identifier="externalId")

        dropped_connections: list[NeatValueWarning] = []
        unexpected_issues: list[NeatIssue] = []
        for issue in issues:
            if isinstance(issue, NeatValueWarning) and issue.value.startswith("Skipping connection"):
                dropped_connections.append(issue)
            else:
                unexpected_issues.append(issue)
        assert not unexpected_issues
        assert len(dropped_connections) == expected_connection_drop

        instances_ids = sorted((id_ for id_, _ in neat._state.instances.store.queries.select.list_instances_ids()))

        expected = sorted(
            [
                CLASSIC_CDF_NAMESPACE[f"{InstanceIdPrefix.file}{fm.external_id}"]
                for fm in file_metadata
                if fm.instance_id is None
                # Neat automatically converts the source string to a new entity
            ]
            + list(
                {
                    CLASSIC_CDF_NAMESPACE[f"ClassicSourceSystem_{fm.source}"]
                    for fm in file_metadata
                    if fm.instance_id is None and fm.source
                }
            )
        )
        assert instances_ids == expected


def test_read_rdf_instances_with_named_graph(tmp_path) -> None:
    """Test reading RDF instances into a named graph"""

    ttl_file = tmp_path / "test.ttl"
    ttl_file.write_text(
        """
        @prefix ex: <http://example.org/> .
        ex:subject1 ex:predicate1 "value1" .
        ex:subject2 ex:predicate2 "value2" .
    """
    )

    neat = NeatSession()

    # Test with string named_graph
    issues = neat.read.rdf.instances(ttl_file, named_graph="my_test_graph")
    assert not issues.has_errors

    expected_graph_uri = NAMED_GRAPH_NAMESPACE["my_test_graph"]
    target_graph = neat._state.instances.store.graph(expected_graph_uri)

    assert target_graph.identifier == expected_graph_uri
