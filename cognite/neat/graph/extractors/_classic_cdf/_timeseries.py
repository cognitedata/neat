from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import cast

import pytz
from cognite.client import CogniteClient
from cognite.client.data_classes import TimeSeries, TimeSeriesList
from pydantic import AnyHttpUrl, ValidationError
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.utils import string_to_ideal_type


class TimeSeriesExtractor(BaseExtractor):
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
        """Extrac timeseries an asset with the given asset_id."""
        for timeseries in self.timeseries:
            yield from self._timeseries2triples(timeseries, self.namespace)

    @classmethod
    def _timeseries2triples(cls, timeseries: TimeSeries, namespace: Namespace) -> list[Triple]:
        id_ = namespace[str(timeseries.id)]

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, namespace.TimeSeries)]

        # Create attributes

        if timeseries.external_id is not None:
            triples.append((id_, namespace.external_id, Literal(timeseries.external_id)))

        if timeseries.name is not None:
            triples.append((id_, namespace.name, Literal(timeseries.name)))

        if timeseries.is_string is not None:
            triples.append((id_, namespace.is_string, Literal(timeseries.is_string)))

        if timeseries.metadata:
            for key, value in timeseries.metadata.items():
                if value:
                    type_aware_value = string_to_ideal_type(value)
                    try:
                        triples.append((id_, namespace[key], URIRef(str(AnyHttpUrl(type_aware_value)))))  # type: ignore
                    except ValidationError:
                        triples.append((id_, namespace[key], Literal(type_aware_value)))

        if timeseries.unit is not None:
            triples.append((id_, namespace.unit, Literal(timeseries.unit)))

        if timeseries.is_step is not None:
            triples.append((id_, namespace.is_step, Literal(timeseries.is_step)))

        if timeseries.description is not None:
            triples.append((id_, namespace.description, Literal(timeseries.description)))

        if timeseries.security_categories is not None:
            for category in timeseries.security_categories:
                triples.append((id_, namespace.security_categories, Literal(category)))

        if timeseries.created_time is not None:
            triples.append(
                (id_, namespace.created_time, Literal(datetime.fromtimestamp(timeseries.created_time / 1000, pytz.utc)))
            )

        if timeseries.last_updated_time is not None:
            triples.append(
                (
                    id_,
                    namespace.last_updated_time,
                    Literal(datetime.fromtimestamp(timeseries.last_updated_time / 1000, pytz.utc)),
                )
            )

        if timeseries.legacy_name is not None:
            triples.append((id_, namespace.legacy_name, Literal(timeseries.legacy_name)))

        # Create connections
        if timeseries.unit_external_id is not None:
            # try to create connection to QUDT unit catalog
            try:
                triples.append((id_, namespace.unit_external_id, URIRef(str(AnyHttpUrl(timeseries.unit_external_id)))))
            except ValidationError:
                triples.append((id_, namespace.unit_external_id, Literal(timeseries.unit_external_id)))

        if timeseries.data_set_id is not None:
            triples.append((id_, namespace.data_set_id, namespace[str(timeseries.data_set_id)]))

        if timeseries.asset_id is not None:
            triples.append((id_, namespace.asset, namespace[str(timeseries.asset_id)]))

        return triples
