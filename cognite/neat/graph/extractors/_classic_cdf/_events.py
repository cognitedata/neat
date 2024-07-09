import json
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
        unpack_metadata (bool, optional): Whether to unpack metadata. Defaults to False, which yields the metadata as
            a JSON string.
    """

    def __init__(
        self,
        events: Iterable[Event],
        namespace: Namespace | None = None,
        unpack_metadata: bool = False,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.events = events
        self.unpack_metadata = unpack_metadata

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        unpack_metadata: bool = False,
    ):
        return cls(
            cast(
                Iterable[Event],
                client.events(data_set_external_ids=data_set_external_id),
            ),
            namespace,
            unpack_metadata,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str,
        namespace: Namespace | None = None,
        unpack_metadata: bool = False,
    ):
        return cls(EventList.load(Path(file_path).read_text()), namespace, unpack_metadata)

    def extract(self) -> Iterable[Triple]:
        """Extract events as triples."""
        for event in self.events:
            yield from self._event2triples(event)

    def _event2triples(self, event: Event) -> list[Triple]:
        id_ = self.namespace[f"Event_{event.id}"]

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, self.namespace.Event)]

        # Create attributes

        if event.external_id:
            triples.append((id_, self.namespace.external_id, Literal(event.external_id)))

        if event.source:
            triples.append((id_, self.namespace.type, Literal(event.source)))

        if event.type:
            triples.append((id_, self.namespace.type, Literal(event.type)))

        if event.subtype:
            triples.append((id_, self.namespace.subtype, Literal(event.subtype)))

        if event.metadata:
            if self.unpack_metadata:
                for key, value in event.metadata.items():
                    if value:
                        type_aware_value = string_to_ideal_type(value)
                        try:
                            triples.append((id_, self.namespace[key], URIRef(str(AnyHttpUrl(type_aware_value)))))  # type: ignore
                        except ValidationError:
                            triples.append((id_, self.namespace[key], Literal(type_aware_value)))
            else:
                triples.append((id_, self.namespace.metadata, Literal(json.dumps(event.metadata))))

        if event.description:
            triples.append((id_, self.namespace.description, Literal(event.description)))

        if event.created_time:
            triples.append(
                (
                    id_,
                    self.namespace.created_time,
                    Literal(datetime.fromtimestamp(event.created_time / 1000, timezone.utc)),
                )
            )

        if event.last_updated_time:
            triples.append(
                (
                    id_,
                    self.namespace.last_updated_time,
                    Literal(datetime.fromtimestamp(event.last_updated_time / 1000, timezone.utc)),
                )
            )

        if event.start_time:
            triples.append(
                (
                    id_,
                    self.namespace.start_time,
                    Literal(datetime.fromtimestamp(event.start_time / 1000, timezone.utc)),
                )
            )

        if event.end_time:
            triples.append(
                (
                    id_,
                    self.namespace.end_time,
                    Literal(datetime.fromtimestamp(event.end_time / 1000, timezone.utc)),
                )
            )

        if event.data_set_id:
            triples.append(
                (
                    id_,
                    self.namespace.data_set_id,
                    self.namespace[f"Dataset_{event.data_set_id}"],
                )
            )

        if event.asset_ids:
            for asset_id in event.asset_ids:
                triples.append((id_, self.namespace.asset, self.namespace[f"Asset_{asset_id}"]))

        return triples
