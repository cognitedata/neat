from collections import defaultdict
from collections.abc import Callable, Iterable, Set
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Relationship, RelationshipList
from rdflib import Namespace

from cognite.neat._utils.auxiliary import create_sha256_hash

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix


class RelationshipsExtractor(ClassicCDFBaseExtractor[Relationship]):
    """Extract data from Cognite Data Fusions Relationships into Neat."""

    _default_rdf_type = "Relationship"
    _instance_id_prefix = InstanceIdPrefix.relationship

    def __init__(
        self,
        items: Iterable[Relationship],
        namespace: Namespace | None = None,
        to_type: Callable[[Relationship], str | None] | None = None,
        total: int | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
        camel_case: bool = True,
        as_write: bool = False,
    ):
        super().__init__(
            items,
            namespace=namespace,
            to_type=to_type,
            total=total,
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
            camel_case=camel_case,
            as_write=as_write,
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

    def _fallback_id(self, item: Relationship) -> str | None:
        if item.external_id and item.source_external_id and item.target_external_id:
            if self._log_target_nodes and item.target_type and item.target_external_id:
                self._target_external_ids_by_type[InstanceIdPrefix.from_str(item.target_type)].add(
                    item.target_external_id
                )
            return create_sha256_hash(item.external_id)
        return None
