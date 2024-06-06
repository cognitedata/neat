import uuid
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import cast
from urllib.parse import quote

import pytz
from cognite.client import CogniteClient
from cognite.client.data_classes import Relationship, RelationshipList
from rdflib import RDF, Literal, Namespace

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple


class RelationshipsExtractor(BaseExtractor):
    def __init__(
        self,
        relationships: Iterable[Relationship],
        namespace: Namespace | None = None,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.relationships = relationships

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
    ):
        return cls(
            cast(Iterable[Relationship], client.relationships(data_set_external_ids=data_set_external_id)), namespace
        )

    @classmethod
    def from_file(cls, file_path: str, namespace: Namespace | None = None):
        return cls(RelationshipList.load(Path(file_path).read_text()), namespace)

    def extract(self) -> Iterable[Triple]:
        """Extracts an asset with the given asset_id."""
        for relationship in self.relationships:
            yield from self._relationship2triples(relationship, self.namespace)

    @classmethod
    def _relationship2triples(cls, relationship: Relationship, namespace: Namespace) -> list[Triple]:
        """Converts an asset to triples."""

        # relationships do not have an internal id, so we generate one
        id_ = namespace[str(uuid.uuid4())]

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, namespace["Relationship"])]

        # Set source and target types
        if relationship.source_type:
            triples.append(
                (
                    id_,
                    namespace.source_type,
                    namespace[relationship.source_type.title()],
                )
            )

        if relationship.target_type:
            triples.append(
                (
                    id_,
                    namespace.target_type,
                    namespace[relationship.target_type.title()],
                )
            )

        # Create attributes
        if relationship.external_id:
            triples.append((id_, namespace.external_id, Literal(relationship.external_id)))

        if relationship.source_external_id:
            triples.append(
                (
                    id_,
                    namespace.source_external_id,
                    Literal(relationship.source_external_id),
                )
            )

        if relationship.target_external_id:
            triples.append(
                (
                    id_,
                    namespace.target_external_id,
                    Literal(relationship.target_external_id),
                )
            )

        if relationship.start_time:
            triples.append(
                (
                    id_,
                    namespace.start_time,
                    Literal(datetime.fromtimestamp(relationship.start_time / 1000, pytz.utc)),
                )
            )

        if relationship.end_time:
            triples.append(
                (
                    id_,
                    namespace.end_time,
                    Literal(datetime.fromtimestamp(relationship.end_time / 1000, pytz.utc)),
                )
            )

        if relationship.created_time:
            triples.append(
                (
                    id_,
                    namespace.created_time,
                    Literal(datetime.fromtimestamp(relationship.created_time / 1000, pytz.utc)),
                )
            )

        if relationship.last_updated_time:
            triples.append(
                (
                    id_,
                    namespace.last_updated_time,
                    Literal(datetime.fromtimestamp(relationship.last_updated_time / 1000, pytz.utc)),
                )
            )

        if relationship.confidence:
            triples.append(
                (
                    id_,
                    namespace.confidence,
                    Literal(relationship.confidence),
                )
            )

        if relationship.labels:
            for label in relationship.labels:
                # external_id can create ill-formed URIs, so we create websafe URIs
                # since labels do not have internal ids, we use the external_id as the id
                triples.append((id_, namespace.label, namespace[quote(label.dump()["externalId"])]))

        # Create connection
        if relationship.data_set_id:
            triples.append((id_, namespace.dataset, namespace[str(relationship.data_set_id)]))

        return triples
