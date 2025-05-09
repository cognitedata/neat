from collections.abc import Iterable
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import DataSet, DataSetList
from cognite.client.utils.useful_types import SequenceNotStr

from ._base import ClassicCDFBaseExtractor, InstanceIdPrefix, T_CogniteResource


class DataSetExtractor(ClassicCDFBaseExtractor[DataSet]):
    """Extract DataSets from Cognite Data Fusions into Neat."""

    _default_rdf_type = "DataSet"
    _instance_id_prefix = InstanceIdPrefix.data_set

    @classmethod
    def _from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: SequenceNotStr[str],  # type: ignore[override]
    ) -> tuple[int | None, Iterable[DataSet]]:
        items = client.data_sets.retrieve_multiple(external_ids=data_set_external_id)
        return len(items), items

    @classmethod
    def _from_hierarchy(
        cls, client: CogniteClient, root_asset_external_id: str
    ) -> tuple[int | None, Iterable[T_CogniteResource]]:
        raise NotImplementedError("DataSets do not have a hierarchy.")

    @classmethod
    def _from_file(cls, file_path: str | Path) -> tuple[int | None, Iterable[DataSet]]:
        data_sets = DataSetList.load(Path(file_path).read_text())
        return len(data_sets), data_sets
