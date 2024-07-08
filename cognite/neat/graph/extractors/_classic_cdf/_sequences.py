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
    """

    def __init__(
        self,
        sequence: Iterable[Sequence],
        namespace: Namespace | None = None,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.sequence = sequence

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
    ):
        return cls(cast(Iterable[Sequence], client.sequences(data_set_external_ids=data_set_external_id)), namespace)

    @classmethod
    def from_file(cls, file_path: str, namespace: Namespace | None = None):
        return cls(SequenceList.load(Path(file_path).read_text()), namespace)

    def extract(self) -> Iterable[Triple]:
        """Extract sequences as triples."""
        for sequence in self.sequence:
            yield from self._sequence2triples(sequence, self.namespace)

    @classmethod
    def _sequence2triples(cls, sequence: Sequence, namespace: Namespace) -> list[Triple]:
        id_ = namespace[f"Sequence_{sequence.id}"]

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, namespace.Sequence)]

        # Create attributes

        if sequence.external_id:
            triples.append((id_, namespace.external_id, Literal(sequence.external_id)))

        if sequence.name:
            triples.append((id_, namespace.name, Literal(sequence.name)))

        if sequence.metadata:
            for key, value in sequence.metadata.items():
                if value:
                    type_aware_value = string_to_ideal_type(value)
                    try:
                        triples.append((id_, namespace[key], URIRef(str(AnyHttpUrl(type_aware_value)))))  # type: ignore
                    except ValidationError:
                        triples.append((id_, namespace[key], Literal(type_aware_value)))

        if sequence.description:
            triples.append((id_, namespace.description, Literal(sequence.description)))

        if sequence.created_time:
            triples.append(
                (
                    id_,
                    namespace.created_time,
                    Literal(datetime.fromtimestamp(sequence.created_time / 1000, timezone.utc)),
                )
            )

        if sequence.last_updated_time:
            triples.append(
                (
                    id_,
                    namespace.last_updated_time,
                    Literal(datetime.fromtimestamp(sequence.last_updated_time / 1000, timezone.utc)),
                )
            )

        if sequence.data_set_id:
            triples.append((id_, namespace.data_set_id, namespace[f"Dataset_{sequence.data_set_id}"]))

        if sequence.asset_id:
            triples.append((id_, namespace.asset, namespace[f"Asset_{sequence.asset_id}"]))

        return triples
