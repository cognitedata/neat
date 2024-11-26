from collections.abc import Iterable
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import TimeSeries, TimeSeriesFilter, TimeSeriesList

from ._base import ClassicCDFBaseExtractor, InstanceIdPrefix


class TimeSeriesExtractor(ClassicCDFBaseExtractor[TimeSeries]):
    """Extract data from Cognite Data Fusions TimeSeries into Neat."""

    _default_rdf_type = "TimeSeries"
    _instance_id_prefix = InstanceIdPrefix.time_series

    @classmethod
    def _from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
    ) -> tuple[int | None, Iterable[TimeSeries]]:
        total = client.time_series.aggregate_count(
            filter=TimeSeriesFilter(data_set_ids=[{"externalId": data_set_external_id}])
        )
        items = client.time_series(data_set_external_ids=data_set_external_id)
        return total, items

    @classmethod
    def _from_hierarchy(
        cls, client: CogniteClient, root_asset_external_id: str
    ) -> tuple[int | None, Iterable[TimeSeries]]:
        total = client.time_series.aggregate_count(
            filter=TimeSeriesFilter(asset_subtree_ids=[{"externalId": root_asset_external_id}])
        )
        items = client.time_series(asset_subtree_external_ids=root_asset_external_id)
        return total, items

    @classmethod
    def _from_file(cls, file_path: str | Path) -> tuple[int | None, Iterable[TimeSeries]]:
        timeseries = TimeSeriesList.load(Path(file_path).read_text())
        return len(timeseries), timeseries
