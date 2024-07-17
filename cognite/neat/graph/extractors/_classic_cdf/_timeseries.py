import json
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
from cognite.neat.utils.auxiliary import string_to_ideal_type


class TimeSeriesExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusions TimeSeries into Neat.

    Args:
        timeseries (Iterable[TimeSeries]): An iterable of timeseries.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        unpack_metadata (bool, optional): Whether to unpack metadata. Defaults to False, which yields the metadata as
            a JSON string.
    """

    def __init__(
        self,
        timeseries: Iterable[TimeSeries],
        namespace: Namespace | None = None,
        unpack_metadata: bool = True,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.timeseries = timeseries
        self.unpack_metadata = unpack_metadata

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        unpack_metadata: bool = True,
    ):
        return cls(
            cast(
                Iterable[TimeSeries],
                client.time_series(data_set_external_ids=data_set_external_id),
            ),
            namespace,
            unpack_metadata,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str,
        namespace: Namespace | None = None,
        unpack_metadata: bool = True,
    ):
        return cls(TimeSeriesList.load(Path(file_path).read_text()), namespace, unpack_metadata)

    def extract(self) -> Iterable[Triple]:
        """Extract timeseries as triples."""
        for timeseries in self.timeseries:
            yield from self._timeseries2triples(timeseries)

    def _timeseries2triples(self, timeseries: TimeSeries) -> list[Triple]:
        id_ = self.namespace[f"TimeSeries_{timeseries.id}"]

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, self.namespace.TimeSeries)]

        # Create attributes

        if timeseries.external_id:
            triples.append((id_, self.namespace.external_id, Literal(timeseries.external_id)))

        if timeseries.name:
            triples.append((id_, self.namespace.name, Literal(timeseries.name)))

        if timeseries.is_string:
            triples.append((id_, self.namespace.is_string, Literal(timeseries.is_string)))

        if timeseries.metadata:
            if self.unpack_metadata:
                for key, value in timeseries.metadata.items():
                    if value:
                        type_aware_value = string_to_ideal_type(value)
                        try:
                            triples.append((id_, self.namespace[key], URIRef(str(AnyHttpUrl(type_aware_value)))))  # type: ignore
                        except ValidationError:
                            triples.append((id_, self.namespace[key], Literal(type_aware_value)))
            else:
                triples.append(
                    (
                        id_,
                        self.namespace.metadata,
                        Literal(json.dumps(timeseries.metadata)),
                    )
                )

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
                    self.namespace[f"Dataset_{timeseries.data_set_id}"],
                )
            )

        if timeseries.asset_id:
            triples.append(
                (
                    id_,
                    self.namespace.asset,
                    self.namespace[f"Asset_{timeseries.asset_id}"],
                )
            )

        return triples
