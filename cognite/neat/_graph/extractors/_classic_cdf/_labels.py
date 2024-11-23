from collections.abc import Callable, Set
from pathlib import Path
from urllib.parse import quote

from cognite.client import CogniteClient
from cognite.client.data_classes import Label, LabelDefinition, LabelDefinitionList
from rdflib import Namespace

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix


class LabelsExtractor(ClassicCDFBaseExtractor[LabelDefinition]):
    """Extract data from Cognite Data Fusions Labels into Neat."""

    _default_rdf_type = "Label"
    _instance_id_prefix = InstanceIdPrefix.label

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

    def _fallback_id(self, item: LabelDefinition) -> str | None:
        if not item.external_id:
            return None
        return self._label_id(item)

    @staticmethod
    def _label_id(label: Label | LabelDefinition | dict) -> str:
        # external_id can create ill-formed URIs, so we create websafe URIs
        # since labels do not have internal ids, we use the external_id as the id
        external_id: str | None = None
        if isinstance(label, dict):
            if "externalId" in label:
                external_id = label["externalId"]
            elif "external_id" in label:
                external_id = label["external_id"]
        else:
            external_id = label.external_id
        if external_id is None:
            raise ValueError("External id must be set of the label")
        return quote(external_id)
