from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from cognite.client import CogniteClient
from cognite.client.data_classes import Event, EventList
from pydantic import AnyHttpUrl, ValidationError
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.utils import string_to_ideal_type


class EventsExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusions Events into Neat.

    Args:
        events (Iterable[Event]): An iterable of events.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
    """

    def __init__(
        self,
        events: Iterable[Event],
        namespace: Namespace | None = None,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.events = events

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
    ):
        return cls(cast(Iterable[Event], client.events(data_set_external_ids=data_set_external_id)), namespace)

    @classmethod
    def from_file(cls, file_path: str, namespace: Namespace | None = None):
        return cls(EventList.load(Path(file_path).read_text()), namespace)

    def extract(self) -> Iterable[Triple]:
        """Extract events as triples."""
        for event in self.events:
            yield from self._event2triples(event, self.namespace)

    @classmethod
    def _event2triples(cls, event: Event, namespace: Namespace) -> list[Triple]:
        id_ = namespace[f"Event_{event.id}"]

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, namespace.Event)]

        # Create attributes

        if event.external_id:
            triples.append((id_, namespace.external_id, Literal(event.external_id)))

        if event.source:
            triples.append((id_, namespace.type, Literal(event.source)))

        if event.type:
            triples.append((id_, namespace.type, Literal(event.type)))

        if event.subtype:
            triples.append((id_, namespace.subtype, Literal(event.subtype)))

        if event.metadata:
            for key, value in event.metadata.items():
                if value:
                    type_aware_value = string_to_ideal_type(value)
                    try:
                        triples.append((id_, namespace[key], URIRef(str(AnyHttpUrl(type_aware_value)))))  # type: ignore
                    except ValidationError:
                        triples.append((id_, namespace[key], Literal(type_aware_value)))

        if event.description:
            triples.append((id_, namespace.description, Literal(event.description)))

        if event.created_time:
            triples.append(
                (id_, namespace.created_time, Literal(datetime.fromtimestamp(event.created_time / 1000, timezone.utc)))
            )

        if event.last_updated_time:
            triples.append(
                (
                    id_,
                    namespace.last_updated_time,
                    Literal(datetime.fromtimestamp(event.last_updated_time / 1000, timezone.utc)),
                )
            )

        if event.start_time:
            triples.append(
                (
                    id_,
                    namespace.start_time,
                    Literal(datetime.fromtimestamp(event.start_time / 1000, timezone.utc)),
                )
            )

        if event.end_time:
            triples.append(
                (
                    id_,
                    namespace.end_time,
                    Literal(datetime.fromtimestamp(event.end_time / 1000, timezone.utc)),
                )
            )

        if event.data_set_id:
            triples.append((id_, namespace.data_set_id, namespace[f"Dataset_{event.data_set_id}"]))

        if event.asset_ids:
            for asset_id in event.asset_ids:
                triples.append((id_, namespace.asset, namespace[f"Asset_{asset_id}"]))

        return triples
