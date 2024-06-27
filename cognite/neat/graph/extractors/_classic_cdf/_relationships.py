from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from urllib.parse import quote

from cognite.client import CogniteClient
from cognite.client.data_classes import Relationship, RelationshipList
from rdflib import RDF, Literal, Namespace

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.utils import create_sha256_hash


class RelationshipsExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusions Relationships into Neat.

    Args:
        relationships (Iterable[Asset]): An iterable of relationships.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
    """

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

        if relationship.external_id and relationship.source_external_id and relationship.target_external_id:
            # relationships do not have an internal id, so we generate one
            id_ = namespace[f"Relationship_{create_sha256_hash(relationship.external_id)}"]

            # Set rdf type
            triples: list[Triple] = [(id_, RDF.type, namespace["Relationship"])]

            # Set source and target types
            if source_type := relationship.source_type:
                triples.append(
                    (
                        id_,
                        namespace.source_type,
                        namespace[source_type.title()],
                    )
                )

            if target_type := relationship.target_type:
                triples.append(
                    (
                        id_,
                        namespace.target_type,
                        namespace[target_type.title()],
                    )
                )

            # Create attributes

            triples.append((id_, namespace.external_id, Literal(relationship.external_id)))

            triples.append(
                (
                    id_,
                    namespace.source_external_id,
                    Literal(relationship.source_external_id),
                )
            )

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
                        Literal(datetime.fromtimestamp(relationship.start_time / 1000, timezone.utc)),
                    )
                )

            if relationship.end_time:
                triples.append(
                    (
                        id_,
                        namespace.end_time,
                        Literal(datetime.fromtimestamp(relationship.end_time / 1000, timezone.utc)),
                    )
                )

            if relationship.created_time:
                triples.append(
                    (
                        id_,
                        namespace.created_time,
                        Literal(datetime.fromtimestamp(relationship.created_time / 1000, timezone.utc)),
                    )
                )

            if relationship.last_updated_time:
                triples.append(
                    (
                        id_,
                        namespace.last_updated_time,
                        Literal(datetime.fromtimestamp(relationship.last_updated_time / 1000, timezone.utc)),
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
                    triples.append((id_, namespace.label, namespace[f"Label_{quote(label.dump()['externalId'])}"]))

            # Create connection
            if relationship.data_set_id:
                triples.append((id_, namespace.dataset, namespace[f"Dataset_{relationship.data_set_id}"]))

            return triples
        return []
