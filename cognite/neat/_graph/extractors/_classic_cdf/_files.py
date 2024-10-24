from collections.abc import Callable, Set
from datetime import datetime, timezone
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import FileMetadata, FileMetadataFilter, FileMetadataList
from rdflib import RDF, Literal, Namespace

from cognite.neat._graph.models import Triple

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix
from ._labels import LabelsExtractor


class FilesExtractor(ClassicCDFBaseExtractor[FileMetadata]):
    """Extract data from Cognite Data Fusions files metadata into Neat.

    Args:
        items (Iterable[FileMetadata]): An iterable of items.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        to_type (Callable[[FileMetadata], str | None], optional): A function to convert an item to a type.
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

    _default_rdf_type = "File"

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

    def _item2triples(self, file: FileMetadata) -> list[Triple]:
        id_ = self.namespace[f"{InstanceIdPrefix.file}{file.id}"]

        type_ = self._get_rdf_type(file)

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, self.namespace[type_])]

        # Create attributes

        if file.external_id:
            triples.append((id_, self.namespace.external_id, Literal(file.external_id)))

        if file.source:
            triples.append((id_, self.namespace.type, Literal(file.source)))

        if file.mime_type:
            triples.append((id_, self.namespace.mime_type, Literal(file.mime_type)))

        if file.uploaded:
            triples.append((id_, self.namespace.uploaded, Literal(file.uploaded)))

        if file.source:
            triples.append((id_, self.namespace.source, Literal(file.source)))

        if file.metadata:
            triples.extend(self._metadata_to_triples(id_, file.metadata))

        if file.source_created_time:
            triples.append(
                (
                    id_,
                    self.namespace.source_created_time,
                    Literal(datetime.fromtimestamp(file.source_created_time / 1000, timezone.utc)),
                )
            )
        if file.source_modified_time:
            triples.append(
                (
                    id_,
                    self.namespace.source_created_time,
                    Literal(datetime.fromtimestamp(file.source_modified_time / 1000, timezone.utc)),
                )
            )
        if file.uploaded_time:
            triples.append(
                (
                    id_,
                    self.namespace.uploaded_time,
                    Literal(datetime.fromtimestamp(file.uploaded_time / 1000, timezone.utc)),
                )
            )

        if file.created_time:
            triples.append(
                (
                    id_,
                    self.namespace.created_time,
                    Literal(datetime.fromtimestamp(file.created_time / 1000, timezone.utc)),
                )
            )

        if file.last_updated_time:
            triples.append(
                (
                    id_,
                    self.namespace.last_updated_time,
                    Literal(datetime.fromtimestamp(file.last_updated_time / 1000, timezone.utc)),
                )
            )

        if file.labels:
            for label in file.labels:
                # external_id can create ill-formed URIs, so we create websafe URIs
                # since labels do not have internal ids, we use the external_id as the id
                triples.append(
                    (
                        id_,
                        self.namespace.label,
                        self.namespace[f"{InstanceIdPrefix.label}{LabelsExtractor._label_id(label)}"],
                    )
                )

        if file.security_categories:
            for category in file.security_categories:
                triples.append((id_, self.namespace.security_categories, Literal(category)))

        if file.data_set_id:
            triples.append(
                (
                    id_,
                    self.namespace.data_set_id,
                    self.namespace[f"{InstanceIdPrefix.data_set}{file.data_set_id}"],
                )
            )

        if file.asset_ids:
            for asset_id in file.asset_ids:
                triples.append((id_, self.namespace.asset, self.namespace[f"{InstanceIdPrefix.asset}{asset_id}"]))

        return triples
