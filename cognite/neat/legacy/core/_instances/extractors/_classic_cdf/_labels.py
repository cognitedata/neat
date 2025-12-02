from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote

from cognite.client import CogniteClient
from cognite.client.data_classes import Label, LabelDefinition, LabelDefinitionList

from ._base import ClassicCDFBaseExtractor, InstanceIdPrefix, T_CogniteResource


class LabelsExtractor(ClassicCDFBaseExtractor[LabelDefinition]):
    """Extract data from Cognite Data Fusions Labels into Neat."""

    _default_rdf_type = "Label"
    _instance_id_prefix = InstanceIdPrefix.label

    @classmethod
    def _from_dataset(
        cls, client: CogniteClient, data_set_external_id: str
    ) -> tuple[int | None, Iterable[LabelDefinition]]:
        items = client.labels(data_set_external_ids=data_set_external_id)
        return None, items

    @classmethod
    def _from_hierarchy(
        cls, client: CogniteClient, root_asset_external_id: str
    ) -> tuple[int | None, Iterable[T_CogniteResource]]:
        raise NotImplementedError("Hierarchy is not supported for labels")

    @classmethod
    def _from_file(cls, file_path: str | Path) -> tuple[int | None, Iterable[LabelDefinition]]:
        labels = LabelDefinitionList.load(Path(file_path).read_text())
        return len(labels), labels

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
