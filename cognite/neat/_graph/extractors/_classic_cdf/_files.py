from collections.abc import Callable, Set
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import FileMetadata, FileMetadataFilter, FileMetadataList
from rdflib import Namespace

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix


class FilesExtractor(ClassicCDFBaseExtractor[FileMetadata]):
    """Extract data from Cognite Data Fusions files metadata into Neat."""

    _default_rdf_type = "File"
    _instance_id_prefix = InstanceIdPrefix.file

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[FileMetadata], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        return cls(
            client.files(data_set_external_ids=data_set_external_id),
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
        to_type: Callable[[FileMetadata], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        total = client.files.aggregate(
            filter=FileMetadataFilter(asset_subtree_ids=[{"externalId": root_asset_external_id}])
        )[0].count

        return cls(
            client.files(asset_subtree_external_ids=[root_asset_external_id]),
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
        to_type: Callable[[FileMetadata], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        file_metadata = FileMetadataList.load(Path(file_path).read_text())
        return cls(
            file_metadata,
            namespace=namespace,
            to_type=to_type,
            limit=limit,
            total=len(file_metadata),
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )
