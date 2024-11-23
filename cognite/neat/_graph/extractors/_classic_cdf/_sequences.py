from collections.abc import Callable, Set
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Sequence, SequenceFilter, SequenceList
from rdflib import Namespace

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix


class SequencesExtractor(ClassicCDFBaseExtractor[Sequence]):
    """Extract data from Cognite Data Fusions Sequences into Neat."""

    _default_rdf_type = "Sequence"
    _instance_id_prefix = InstanceIdPrefix.sequence

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
