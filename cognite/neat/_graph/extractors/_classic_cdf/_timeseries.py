from collections.abc import Callable, Set
from datetime import datetime, timezone
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import TimeSeries, TimeSeriesFilter, TimeSeriesList
from pydantic import AnyHttpUrl, ValidationError
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat._graph.models import Triple

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
    """

    _default_rdf_type = "TimeSeries"

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

    def _item2triples(self, timeseries: TimeSeries) -> list[Triple]:
        id_ = self.namespace[f"{InstanceIdPrefix.time_series}{timeseries.id}"]

        # Set rdf type
        type_ = self._get_rdf_type(timeseries)
        triples: list[Triple] = [(id_, RDF.type, self.namespace[type_])]

        # Create attributes
        if timeseries.external_id:
            triples.append((id_, self.namespace.external_id, Literal(timeseries.external_id)))

        if timeseries.name:
            triples.append((id_, self.namespace.name, Literal(timeseries.name)))

        if timeseries.is_string:
            triples.append((id_, self.namespace.is_string, Literal(timeseries.is_string)))

        if timeseries.metadata:
            triples.extend(self._metadata_to_triples(id_, timeseries.metadata))

        if timeseries.unit:
            triples.append((id_, self.namespace.unit, Literal(timeseries.unit)))

        if self.namespace.is_step:
            triples.append((id_, self.namespace.is_step, Literal(timeseries.is_step)))

        if timeseries.description:
            triples.append((id_, self.namespace.description, Literal(timeseries.description)))

        if timeseries.security_categories:
            for category in timeseries.security_categories:
                triples.append((id_, self.namespace.security_categories, Literal(category)))

        if timeseries.created_time:
            triples.append(
                (
                    id_,
                    self.namespace.created_time,
                    Literal(datetime.fromtimestamp(timeseries.created_time / 1000, timezone.utc)),
                )
            )

        if timeseries.last_updated_time:
            triples.append(
                (
                    id_,
                    self.namespace.last_updated_time,
                    Literal(datetime.fromtimestamp(timeseries.last_updated_time / 1000, timezone.utc)),
                )
            )

        if timeseries.legacy_name:
            triples.append((id_, self.namespace.legacy_name, Literal(timeseries.legacy_name)))

        # Create connections
        if timeseries.unit_external_id:
            # try to create connection to QUDT unit catalog
            try:
                triples.append(
                    (
                        id_,
                        self.namespace.unit_external_id,
                        URIRef(str(AnyHttpUrl(timeseries.unit_external_id))),
                    )
                )
            except ValidationError:
                triples.append(
                    (
                        id_,
                        self.namespace.unit_external_id,
                        Literal(timeseries.unit_external_id),
                    )
                )

        if timeseries.data_set_id:
            triples.append(
                (
                    id_,
                    self.namespace.dataset,
                    self.namespace[f"{InstanceIdPrefix.data_set}{timeseries.data_set_id}"],
                )
            )

        if timeseries.asset_id:
            triples.append(
                (
                    id_,
                    self.namespace.asset,
                    self.namespace[f"{InstanceIdPrefix.asset}{timeseries.asset_id}"],
                )
            )

        return triples
