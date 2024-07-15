import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from urllib.parse import quote

from cognite.client import CogniteClient
from cognite.client.data_classes import FileMetadata, FileMetadataList
from pydantic import AnyHttpUrl, ValidationError
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.utils import string_to_ideal_type


class FilesExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusions files metadata into Neat.

    Args:
        files_metadata (Iterable[FileMetadata]): An iterable of files metadata.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        unpack_metadata (bool, optional): Whether to unpack metadata. Defaults to False, which yields the metadata as
            a JSON string.
    """

    def __init__(
        self,
        files_metadata: Iterable[FileMetadata],
        namespace: Namespace | None = None,
        unpack_metadata: bool = True,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.files_metadata = files_metadata
        self.unpack_metadata = unpack_metadata

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        unpack_metadata: bool = True,
    ):
        return cls(
            cast(
                Iterable[FileMetadata],
                client.files(data_set_external_ids=data_set_external_id),
            ),
            namespace,
            unpack_metadata,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str,
        namespace: Namespace | None = None,
        unpack_metadata: bool = True,
    ):
        return cls(
            FileMetadataList.load(Path(file_path).read_text()),
            namespace,
            unpack_metadata,
        )

    def extract(self) -> Iterable[Triple]:
        """Extract files metadata as triples."""
        for event in self.files_metadata:
            yield from self._file2triples(event)

    def _file2triples(self, file: FileMetadata) -> list[Triple]:
        id_ = self.namespace[f"File_{file.id}"]

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, self.namespace.File)]

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
            if self.unpack_metadata:
                for key, value in file.metadata.items():
                    if value:
                        type_aware_value = string_to_ideal_type(value)
                        try:
                            triples.append((id_, self.namespace[key], URIRef(str(AnyHttpUrl(type_aware_value)))))  # type: ignore
                        except ValidationError:
                            triples.append((id_, self.namespace[key], Literal(type_aware_value)))
            else:
                triples.append((id_, self.namespace.metadata, Literal(json.dumps(file.metadata))))

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
                        self.namespace[f"Label_{quote(label.dump()['externalId'])}"],
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
                    self.namespace[f"Dataset_{file.data_set_id}"],
                )
            )

        if file.asset_ids:
            for asset_id in file.asset_ids:
                triples.append((id_, self.namespace.asset, self.namespace[f"Asset_{asset_id}"]))

        return triples
