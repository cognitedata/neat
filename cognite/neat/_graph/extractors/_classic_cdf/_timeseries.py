from collections.abc import Callable, Set
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import TimeSeries, TimeSeriesFilter, TimeSeriesList
from rdflib import Namespace

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix


class TimeSeriesExtractor(ClassicCDFBaseExtractor[TimeSeries]):
    """Extract data from Cognite Data Fusions TimeSeries into Neat.

    Args:
        items (Iterable[TimeSeries]): An iterable of items.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        to_type (Callable[[TimeSeries], str | None], optional): A function to convert an item to a type.
            Defaults to None. If None or if the function returns None, the asset will be set to the default type.
        total (int, optional): The total number of items to load. If passed, you will get a progress bar if rich
            is installed. Defaults to None.
        limit (int, optional): The maximal number of items to load. Defaults to None. This is typically used for
            testing setup of the extractor. For example, if you are extracting 100 000 assets, you might want to
            limit the extraction to 1000 assets to test the setup.
        unpack_metadata (bool, optional): Whether to unpack metadata. Defaults to False, which yields the metadata as
            a JSON string.
        skip_metadata_values (set[str] | frozenset[str] | None, optional): If you are unpacking metadata, then
           values in this set will be skipped.
        camel_case (bool, optional): Whether to use camelCase instead of snake_case for property names.
            Defaults to True.
    """

    _default_rdf_type = "TimeSeries"
    _instance_id_prefix = InstanceIdPrefix.time_series

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[TimeSeries], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        total = client.time_series.aggregate_count(
            filter=TimeSeriesFilter(data_set_ids=[{"externalId": data_set_external_id}])
        )

        return cls(
            client.time_series(data_set_external_ids=data_set_external_id),
            total=total,
            namespace=namespace,
            to_type=to_type,
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    @classmethod
    def from_hierarchy(
        cls,
        client: CogniteClient,
        root_asset_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[TimeSeries], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        total = client.time_series.aggregate_count(
            filter=TimeSeriesFilter(asset_subtree_ids=[{"externalId": root_asset_external_id}])
        )

        return cls(
            client.time_series(asset_external_ids=[root_asset_external_id]),
            namespace,
            to_type,
            total,
            limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str,
        namespace: Namespace | None = None,
        to_type: Callable[[TimeSeries], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        timeseries = TimeSeriesList.load(Path(file_path).read_text())
        return cls(
            timeseries,
            total=len(timeseries),
            namespace=namespace,
            to_type=to_type,
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )
