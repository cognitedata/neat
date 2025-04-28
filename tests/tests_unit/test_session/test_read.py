from cognite.client.data_classes import TimeSeriesList

from cognite.neat import NeatSession
from cognite.neat._client.testing import monkeypatch_neat_client
from cognite.neat._constants import CLASSIC_CDF_NAMESPACE
from cognite.neat._graph.extractors._classic_cdf._base import InstanceIdPrefix
from tests.data import InstanceData


class TestReadClassicTimeSeries:
    def test_read_times_series(self) -> None:
        with monkeypatch_neat_client() as client:
            timeseries = TimeSeriesList.load(InstanceData.AssetCentricCDF.timeseries_yaml.read_text(encoding="utf-8"))
            client.time_series.aggregate_count.return_value = len(timeseries)
            client.time_series.return_value = timeseries

            neat: NeatSession = NeatSession(client)

        neat.read.cdf.classic.time_series("my_data_set", identifier="externalId")

        instances_ids = sorted((id_ for id_, _ in neat._state.instances.store.queries.select.list_instances_ids()))

        expected = sorted(
            [CLASSIC_CDF_NAMESPACE[f"{InstanceIdPrefix.time_series}{ts.external_id}"] for ts in timeseries]
        )
        assert instances_ids == expected
