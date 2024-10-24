from collections.abc import Callable, Set
from datetime import datetime, timezone
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Sequence, SequenceFilter, SequenceList
from rdflib import RDF, Literal, Namespace

from cognite.neat._graph.models import Triple

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix


class SequencesExtractor(ClassicCDFBaseExtractor[Sequence]):
    """Extract data from Cognite Data Fusions Sequences into Neat.

    Args:
        items (Iterable[Sequence]): An iterable of items.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        to_type (Callable[[Sequence], str | None], optional): A function to convert an item to a type.
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

    _default_rdf_type = "Sequence"

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Sequence], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        total = client.sequences.aggregate_count(
            filter=SequenceFilter(data_set_ids=[{"externalId": data_set_external_id}])
        )
        return cls(
            client.sequences(data_set_external_ids=data_set_external_id),
            total=total,
            namespace=namespace,
            to_type=to_type,
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    @classmethod
    def from_hierarchy(
        cls,
        client: CogniteClient,
        root_asset_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Sequence], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        total = client.sequences.aggregate_count(
            filter=SequenceFilter(asset_subtree_ids=[{"externalId": root_asset_external_id}])
        )

        return cls(
            client.sequences(asset_subtree_external_ids=[root_asset_external_id]),
            namespace,
            to_type,
            total,
            limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Sequence], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        sequences = SequenceList.load(Path(file_path).read_text())
        return cls(
            sequences,
            total=len(sequences),
            namespace=namespace,
            to_type=to_type,
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    def _item2triples(self, sequence: Sequence) -> list[Triple]:
        id_ = self.namespace[f"{InstanceIdPrefix.sequence}{sequence.id}"]

        type_ = self._get_rdf_type(sequence)
        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, self.namespace[type_])]

        # Create attributes

        if sequence.external_id:
            triples.append((id_, self.namespace.external_id, Literal(sequence.external_id)))

        if sequence.name:
            triples.append((id_, self.namespace.name, Literal(sequence.name)))

        if sequence.metadata:
            triples.extend(self._metadata_to_triples(id_, sequence.metadata))

        if sequence.description:
            triples.append((id_, self.namespace.description, Literal(sequence.description)))

        if sequence.created_time:
            triples.append(
                (
                    id_,
                    self.namespace.created_time,
                    Literal(datetime.fromtimestamp(sequence.created_time / 1000, timezone.utc)),
                )
            )

        if sequence.last_updated_time:
            triples.append(
                (
                    id_,
                    self.namespace.last_updated_time,
                    Literal(datetime.fromtimestamp(sequence.last_updated_time / 1000, timezone.utc)),
                )
            )

        if sequence.data_set_id:
            triples.append(
                (
                    id_,
                    self.namespace.data_set_id,
                    self.namespace[f"{InstanceIdPrefix.data_set}{sequence.data_set_id}"],
                )
            )

        if sequence.asset_id:
            triples.append(
                (
                    id_,
                    self.namespace.asset,
                    self.namespace[f"{InstanceIdPrefix.asset}{sequence.asset_id}"],
                )
            )

        return triples
