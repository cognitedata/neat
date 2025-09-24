from collections.abc import Iterable
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import FileMetadata, FileMetadataFilter, FileMetadataList

from ._base import ClassicCDFBaseExtractor, InstanceIdPrefix


class FilesExtractor(ClassicCDFBaseExtractor[FileMetadata]):
    """Extract data from Cognite Data Fusions files metadata into Neat."""

    _default_rdf_type = "File"
    _instance_id_prefix = InstanceIdPrefix.file

    @classmethod
    def _from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
    ) -> tuple[int | None, Iterable[FileMetadata]]:
        items = client.files(data_set_external_ids=data_set_external_id)
        return None, cls._filter_out_instance_id(items)

    @classmethod
    def _from_hierarchy(
        cls, client: CogniteClient, root_asset_external_id: str
    ) -> tuple[int | None, Iterable[FileMetadata]]:
        total = client.files.aggregate(
            filter=FileMetadataFilter(asset_subtree_ids=[{"externalId": root_asset_external_id}])
        )[0].count
        items = client.files(asset_subtree_external_ids=root_asset_external_id)
        return total, cls._filter_out_instance_id(items)

    @classmethod
    def _from_file(cls, file_path: str | Path) -> tuple[int | None, Iterable[FileMetadata]]:
        file_metadata = FileMetadataList.load(Path(file_path).read_text())
        return len(file_metadata), cls._filter_out_instance_id(file_metadata)

    @classmethod
    def _filter_out_instance_id(cls, items: Iterable[FileMetadata]) -> Iterable[FileMetadata]:
        """Filter out TimeSeries with InstanceId."""
        # If the InstanceId is not None, it means that the TimeSeries is already connected to CogniteTimeSeries in DMS.
        # We do not want to download it again.
        return (item for item in items if item.instance_id is None)
