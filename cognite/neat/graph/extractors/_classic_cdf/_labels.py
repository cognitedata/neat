from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from cognite.client import CogniteClient
from cognite.client.data_classes import LabelDefinition, LabelDefinitionList
from rdflib import RDF, Literal, Namespace

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.utils import create_sha256_hash


class LabelsExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusions Labels into Neat.

    Args:
        labels (Iterable[LabelDefinition]): An iterable of labels.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
    """

    def __init__(
        self,
        labels: Iterable[LabelDefinition],
        namespace: Namespace | None = None,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.labels = labels

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
    ):
        return cls(
            cast(Iterable[LabelDefinition], client.labels(data_set_external_ids=data_set_external_id)), namespace
        )

    @classmethod
    def from_file(cls, file_path: str, namespace: Namespace | None = None):
        return cls(LabelDefinitionList.load(Path(file_path).read_text()), namespace)

    def extract(self) -> Iterable[Triple]:
        """Extract labels as triples."""
        for label in self.labels:
            yield from self._labels2triples(label, self.namespace)

    @classmethod
    def _labels2triples(cls, label: LabelDefinition, namespace: Namespace) -> list[Triple]:
        if label.external_id:
            id_ = namespace[f"Label_{create_sha256_hash(label.external_id)}"]

            # Set rdf type
            triples: list[Triple] = [(id_, RDF.type, namespace.Label)]

            # Create attributes
            triples.append((id_, namespace.external_id, Literal(label.external_id)))

            if label.name:
                triples.append((id_, namespace.name, Literal(label.name)))

            if label.description:
                triples.append((id_, namespace.description, Literal(label.description)))

            if label.created_time:
                triples.append(
                    (
                        id_,
                        namespace.created_time,
                        Literal(datetime.fromtimestamp(label.created_time / 1000, timezone.utc)),
                    )
                )

            if label.data_set_id:
                triples.append((id_, namespace.data_set_id, namespace[f"Dataset_{label.data_set_id}"]))

            return triples
        return []
