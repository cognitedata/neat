import typing
import warnings
from collections import defaultdict
from collections.abc import Callable, Iterable, Set
from pathlib import Path
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes import Relationship, RelationshipList
from rdflib import Namespace, URIRef

from cognite.neat._issues.warnings import NeatValueWarning
from cognite.neat._shared import Triple
from cognite.neat._utils.auxiliary import create_sha256_hash

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix, T_CogniteResource


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
        prefix: str | None = None,
        identifier: typing.Literal["id", "externalId"] = "id",
    ):
        # This is used by the ClassicExtractor to log the target nodes, such
        # that it can extract them.
        # It is private to avoid exposing it to the user.
        self._target_external_ids_by_type: dict[InstanceIdPrefix, set[str]] = defaultdict(set)
        self._log_target_nodes = False
        # Ensure that this becomes an iterator, even if it is a list.
        to_iterate = (self._log_target_nodes_if_set(item) for item in items)
        super().__init__(
            to_iterate,
            namespace=namespace,
            to_type=to_type,
            total=total,
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
            camel_case=camel_case,
            as_write=as_write,
            prefix=prefix,
            identifier=identifier,
        )
        self._uri_by_external_id_by_by_type: dict[InstanceIdPrefix, dict[str, URIRef]] = defaultdict(dict)
        self._target_triples: list[tuple[URIRef, URIRef, str, str]] = []

    def _log_target_nodes_if_set(self, item: Relationship) -> Relationship:
        if not self._log_target_nodes:
            return item
        if item.target_type and item.target_external_id:
            self._target_external_ids_by_type[InstanceIdPrefix.from_str(item.target_type)].add(item.target_external_id)
        return item

    def _item2triples_special_cases(self, id_: URIRef, dumped: dict[str, Any]) -> list[Triple]:
        if self.identifier == "externalId":
            return []
        triples: list[Triple] = []
        if (source_external_id := dumped.pop("sourceExternalId")) and "sourceType" in dumped:
            source_type = dumped["sourceType"]
            try:
                source_uri = self._uri_by_external_id_by_by_type[InstanceIdPrefix.from_str(source_type)][
                    source_external_id
                ]
            except KeyError:
                warnings.warn(
                    NeatValueWarning(f"Missing externalId {source_external_id} for {source_type}"), stacklevel=2
                )
            else:
                triples.append((id_, self.namespace["sourceExternalId"], source_uri))
        if (target_external_id := dumped.pop("targetExternalId")) and "targetType" in dumped:
            target_type = dumped["targetType"]
            # We do not yet have the target nodes, so we log them for later extraction.
            self._target_triples.append((id_, self.namespace["targetExternalId"], target_type, target_external_id))
        return triples

    @classmethod
    def _from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
    ) -> tuple[int | None, Iterable[Relationship]]:
        items = client.relationships(data_set_external_ids=data_set_external_id)
        return None, items

    @classmethod
    def _from_hierarchy(
        cls, client: CogniteClient, root_asset_external_id: str
    ) -> tuple[int | None, Iterable[T_CogniteResource]]:
        raise NotImplementedError("Relationships do not have a hierarchy.")

    @classmethod
    def _from_file(cls, file_path: str | Path) -> tuple[int | None, Iterable[Relationship]]:
        relationships = RelationshipList.load(Path(file_path).read_text())
        return len(relationships), relationships

    def _fallback_id(self, item: Relationship) -> str | None:
        if item.external_id:
            return create_sha256_hash(item.external_id)
        return None
