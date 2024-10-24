from collections.abc import Callable, Set
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from cognite.client import CogniteClient
from cognite.client.data_classes import Label, LabelDefinition, LabelDefinitionList
from rdflib import RDF, Literal, Namespace

from cognite.neat._graph.models import Triple

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix


class LabelsExtractor(ClassicCDFBaseExtractor[LabelDefinition]):
    """Extract data from Cognite Data Fusions Labels into Neat.

    Args:
        items (Iterable[LabelDefinition]): An iterable of items.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        to_type (Callable[[LabelDefinition], str | None], optional): A function to convert an item to a type.
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

    _default_rdf_type = "Label"

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[LabelDefinition], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        return cls(
            client.labels(data_set_external_ids=data_set_external_id),
            namespace=namespace,
            to_type=to_type,
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str,
        namespace: Namespace | None = None,
        to_type: Callable[[LabelDefinition], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        labels = LabelDefinitionList.load(Path(file_path).read_text())
        return cls(
            labels,
            total=len(labels),
            namespace=namespace,
            to_type=to_type,
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    def _item2triples(self, label: LabelDefinition) -> list[Triple]:
        if not label.external_id:
            return []

        id_ = self.namespace[f"{InstanceIdPrefix.label}{self._label_id(label)}"]

        type_ = self._get_rdf_type(label)
        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, self.namespace[type_])]

        # Create attributes
        triples.append((id_, self.namespace.external_id, Literal(label.external_id)))

        if label.name:
            triples.append((id_, self.namespace.name, Literal(label.name)))

        if label.description:
            triples.append((id_, self.namespace.description, Literal(label.description)))

        if label.created_time:
            triples.append(
                (
                    id_,
                    self.namespace.created_time,
                    Literal(datetime.fromtimestamp(label.created_time / 1000, timezone.utc)),
                )
            )

        if label.data_set_id:
            triples.append(
                (
                    id_,
                    self.namespace.data_set_id,
                    self.namespace[f"{InstanceIdPrefix.data_set}{label.data_set_id}"],
                )
            )

        return triples

    @staticmethod
    def _label_id(label: Label | LabelDefinition) -> str:
        # external_id can create ill-formed URIs, so we create websafe URIs
        # since labels do not have internal ids, we use the external_id as the id
        if label.external_id is None:
            raise ValueError("External id must be set of the label")
        return quote(label.external_id)
