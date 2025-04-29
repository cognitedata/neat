from cognite.client.data_classes import TimeSeriesList
from cognite.client.data_classes.data_modeling import NodeId

from cognite.neat import NeatSession
from cognite.neat._client.testing import monkeypatch_neat_client
from cognite.neat._constants import CLASSIC_CDF_NAMESPACE
from cognite.neat._graph.extractors._classic_cdf._base import InstanceIdPrefix
from cognite.neat._issues.warnings import NeatValueWarning
from tests.data import InstanceData


class TestReadClassicTimeSeries:
    def test_read_times_series(self) -> None:
        with monkeypatch_neat_client() as client:
            timeseries = TimeSeriesList.load(InstanceData.AssetCentricCDF.timeseries_yaml.read_text(encoding="utf-8"))
            assert len(timeseries) >= 2
            # TimeSeries with InstanceId should be skipped
            timeseries[0].instance_id = NodeId("already", "connected")
            client.time_series.aggregate_count.return_value = len(timeseries)
            client.time_series.return_value = timeseries

            neat: NeatSession = NeatSession(client)

        issues = neat.read.cdf.classic.time_series("my_data_set", identifier="externalId")
        unexpected_type = [
            issue
            for issue in issues
            if not (isinstance(issue, NeatValueWarning) and issue.value.startswith("Skipping connection"))
        ]
        assert not unexpected_type

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
