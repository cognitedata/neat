import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from cognite.client import CogniteClient
from cognite.client.data_classes import Sequence, SequenceList
from pydantic import AnyHttpUrl, ValidationError
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.utils import string_to_ideal_type


class SequencesExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusions Sequences into Neat.

    Args:
        sequence (Iterable[Sequence]): An iterable of sequences.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        unpack_metadata (bool, optional): Whether to unpack metadata. Defaults to False, which yields the metadata as
            a JSON string.
    """

    def __init__(
        self,
        sequence: Iterable[Sequence],
        namespace: Namespace | None = None,
        unpack_metadata: bool = False,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.sequence = sequence
        self.unpack_metadata = unpack_metadata

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        unpack_metadata: bool = False,
    ):
        return cls(
            cast(
                Iterable[Sequence],
                client.sequences(data_set_external_ids=data_set_external_id),
            ),
            namespace,
            unpack_metadata,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str,
        namespace: Namespace | None = None,
        unpack_metadata: bool = False,
    ):
        return cls(SequenceList.load(Path(file_path).read_text()), namespace, unpack_metadata)

    def extract(self) -> Iterable[Triple]:
        """Extract sequences as triples."""
        for sequence in self.sequence:
            yield from self._sequence2triples(sequence)

    def _sequence2triples(self, sequence: Sequence) -> list[Triple]:
        id_ = self.namespace[f"Sequence_{sequence.id}"]

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, self.namespace.Sequence)]

        # Create attributes

        if sequence.external_id:
            triples.append((id_, self.namespace.external_id, Literal(sequence.external_id)))

        if sequence.name:
            triples.append((id_, self.namespace.name, Literal(sequence.name)))

        if sequence.metadata:
            if self.unpack_metadata:
                for key, value in sequence.metadata.items():
                    if value:
                        type_aware_value = string_to_ideal_type(value)
                        try:
                            triples.append((id_, self.namespace[key], URIRef(str(AnyHttpUrl(type_aware_value)))))  # type: ignore
                        except ValidationError:
                            triples.append((id_, self.namespace[key], Literal(type_aware_value)))
            else:
                triples.append(
                    (
                        id_,
                        self.namespace.metadata,
                        Literal(json.dumps(sequence.metadata)),
                    )
                )

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
                    self.namespace[f"Dataset_{sequence.data_set_id}"],
                )
            )

        if sequence.asset_id:
            triples.append(
                (
                    id_,
                    self.namespace.asset,
                    self.namespace[f"Asset_{sequence.asset_id}"],
                )
            )

        return triples
