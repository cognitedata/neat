from collections import defaultdict
from collections.abc import Callable, Iterable, Set
from datetime import datetime, timezone
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Relationship, RelationshipList
from rdflib import RDF, Literal, Namespace

from cognite.neat._graph.models import Triple
from cognite.neat._utils.auxiliary import create_sha256_hash

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix
from ._labels import LabelsExtractor


class RelationshipsExtractor(ClassicCDFBaseExtractor[Relationship]):
    """Extract data from Cognite Data Fusions Relationships into Neat.

    Args:
        items (Iterable[Relationship]): An iterable of items.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        to_type (Callable[[Relationship], str | None], optional): A function to convert an item to a type.
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

    _default_rdf_type = "Relationship"

    def __init__(
        self,
        items: Iterable[Relationship],
        namespace: Namespace | None = None,
        to_type: Callable[[Relationship], str | None] | None = None,
        total: int | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        super().__init__(
            items,
            namespace=namespace,
            to_type=to_type,
            total=total,
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )
        # This is used by the ClassicExtractor to log the target nodes, such
        # that it can extract them.
        # It is private to avoid exposing it to the user.
        self._log_target_nodes = False
        self._target_external_ids_by_type: dict[InstanceIdPrefix, set[str]] = defaultdict(set)

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Relationship], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        return cls(
            client.relationships(data_set_external_ids=data_set_external_id),
            namespace=namespace,
            to_type=to_type,
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Relationship], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        relationships = RelationshipList.load(Path(file_path).read_text())
        return cls(
            relationships,
            namespace=namespace,
            total=len(relationships),
            to_type=to_type,
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    def _item2triples(self, relationship: Relationship) -> list[Triple]:
        """Converts an asset to triples."""

        if relationship.external_id and relationship.source_external_id and relationship.target_external_id:
            if self._log_target_nodes and relationship.target_type and relationship.target_external_id:
                self._target_external_ids_by_type[InstanceIdPrefix.from_str(relationship.target_type)].add(
                    relationship.target_external_id
                )

            # relationships do not have an internal id, so we generate one
            id_ = self.namespace[f"{InstanceIdPrefix.relationship}{create_sha256_hash(relationship.external_id)}"]

            type_ = self._get_rdf_type(relationship)
            # Set rdf type
            triples: list[Triple] = [(id_, RDF.type, self.namespace[type_])]

            # Set source and target types
            if source_type := relationship.source_type:
                triples.append(
                    (
                        id_,
                        self.namespace.source_type,
                        self.namespace[source_type.title()],
                    )
                )

            if target_type := relationship.target_type:
                triples.append(
                    (
                        id_,
                        self.namespace.target_type,
                        self.namespace[target_type.title()],
                    )
                )

            # Create attributes

            triples.append((id_, self.namespace.external_id, Literal(relationship.external_id)))

            triples.append(
                (
                    id_,
                    self.namespace.source_external_id,
                    Literal(relationship.source_external_id),
                )
            )

            triples.append(
                (
                    id_,
                    self.namespace.target_external_id,
                    Literal(relationship.target_external_id),
                )
            )

            if relationship.start_time:
                triples.append(
                    (
                        id_,
                        self.namespace.start_time,
                        Literal(datetime.fromtimestamp(relationship.start_time / 1000, timezone.utc)),
                    )
                )

            if relationship.end_time:
                triples.append(
                    (
                        id_,
                        self.namespace.end_time,
                        Literal(datetime.fromtimestamp(relationship.end_time / 1000, timezone.utc)),
                    )
                )

            if relationship.created_time:
                triples.append(
                    (
                        id_,
                        self.namespace.created_time,
                        Literal(datetime.fromtimestamp(relationship.created_time / 1000, timezone.utc)),
                    )
                )

            if relationship.last_updated_time:
                triples.append(
                    (
                        id_,
                        self.namespace.last_updated_time,
                        Literal(datetime.fromtimestamp(relationship.last_updated_time / 1000, timezone.utc)),
                    )
                )

            if relationship.confidence:
                triples.append(
                    (
                        id_,
                        self.namespace.confidence,
                        Literal(relationship.confidence),
                    )
                )

            if relationship.labels:
                for label in relationship.labels:
                    # external_id can create ill-formed URIs, so we create websafe URIs
                    # since labels do not have internal ids, we use the external_id as the id
                    triples.append(
                        (
                            id_,
                            self.namespace.label,
                            self.namespace[f"{InstanceIdPrefix.label}{LabelsExtractor._label_id(label)}"],
                        )
                    )

            # Create connection
            if relationship.data_set_id:
                triples.append(
                    (
                        id_,
                        self.namespace.dataset,
                        self.namespace[f"{InstanceIdPrefix.data_set}{relationship.data_set_id}"],
                    )
                )

            return triples
        return []
