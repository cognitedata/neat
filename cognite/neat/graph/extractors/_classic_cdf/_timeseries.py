from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from cognite.client import CogniteClient
from cognite.client.data_classes import TimeSeries, TimeSeriesList
from pydantic import AnyHttpUrl, ValidationError
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.utils import string_to_ideal_type


class TimeSeriesExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusions TimeSeries into Neat.

    Args:
        timeseries (Iterable[TimeSeries]): An iterable of timeseries.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
    """

    def __init__(
        self,
        timeseries: Iterable[TimeSeries],
        namespace: Namespace | None = None,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.timeseries = timeseries

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
    ):
        return cls(
            cast(Iterable[TimeSeries], client.time_series(data_set_external_ids=data_set_external_id)), namespace
        )

    @classmethod
    def from_file(cls, file_path: str, namespace: Namespace | None = None):
        return cls(TimeSeriesList.load(Path(file_path).read_text()), namespace)

    def extract(self) -> Iterable[Triple]:
        """Extract timeseries as triples."""
        for timeseries in self.timeseries:
            yield from self._timeseries2triples(timeseries, self.namespace)

    @classmethod
    def _timeseries2triples(cls, timeseries: TimeSeries, namespace: Namespace) -> list[Triple]:
        id_ = namespace[f"TimeSeries_{timeseries.id}"]

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, namespace.TimeSeries)]

        # Create attributes

        if timeseries.external_id:
            triples.append((id_, namespace.external_id, Literal(timeseries.external_id)))

        if timeseries.name:
            triples.append((id_, namespace.name, Literal(timeseries.name)))

        if timeseries.is_string:
            triples.append((id_, namespace.is_string, Literal(timeseries.is_string)))

        if timeseries.metadata:
            for key, value in timeseries.metadata.items():
                if value:
                    type_aware_value = string_to_ideal_type(value)
                    try:
                        triples.append((id_, namespace[key], URIRef(str(AnyHttpUrl(type_aware_value)))))  # type: ignore
                    except ValidationError:
                        triples.append((id_, namespace[key], Literal(type_aware_value)))

        if timeseries.unit:
            triples.append((id_, namespace.unit, Literal(timeseries.unit)))

        if namespace.is_step:
            triples.append((id_, namespace.is_step, Literal(timeseries.is_step)))

        if timeseries.description:
            triples.append((id_, namespace.description, Literal(timeseries.description)))

        if timeseries.security_categories:
            for category in timeseries.security_categories:
                triples.append((id_, namespace.security_categories, Literal(category)))

        if timeseries.created_time:
            triples.append(
                (
                    id_,
                    namespace.created_time,
                    Literal(datetime.fromtimestamp(timeseries.created_time / 1000, timezone.utc)),
                )
            )

        if timeseries.last_updated_time:
            triples.append(
                (
                    id_,
                    namespace.last_updated_time,
                    Literal(datetime.fromtimestamp(timeseries.last_updated_time / 1000, timezone.utc)),
                )
            )

        if timeseries.legacy_name:
            triples.append((id_, namespace.legacy_name, Literal(timeseries.legacy_name)))

        # Create connections
        if timeseries.unit_external_id:
            # try to create connection to QUDT unit catalog
            try:
                triples.append((id_, namespace.unit_external_id, URIRef(str(AnyHttpUrl(timeseries.unit_external_id)))))
            except ValidationError:
                triples.append((id_, namespace.unit_external_id, Literal(timeseries.unit_external_id)))

        if timeseries.data_set_id:
            triples.append((id_, namespace.dataset, namespace[f"Dataset_{timeseries.data_set_id}"]))

        if timeseries.asset_id:
            triples.append((id_, namespace.asset, namespace[f"Asset_{timeseries.asset_id}"]))

        return triples
