from collections.abc import Iterable
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Sequence, SequenceFilter, SequenceList

from ._base import ClassicCDFBaseExtractor, InstanceIdPrefix


class SequencesExtractor(ClassicCDFBaseExtractor[Sequence]):
    """Extract data from Cognite Data Fusions Sequences into Neat."""

    _default_rdf_type = "Sequence"
    _instance_id_prefix = InstanceIdPrefix.sequence

    @classmethod
    def _from_dataset(cls, client: CogniteClient, data_set_external_id: str) -> tuple[int | None, Iterable[Sequence]]:
        total = client.sequences.aggregate_count(
            filter=SequenceFilter(data_set_ids=[{"externalId": data_set_external_id}])
        )
        items = client.sequences(data_set_external_ids=data_set_external_id)
        return total, items

    @classmethod
    def _from_hierarchy(
        cls, client: CogniteClient, root_asset_external_id: str
    ) -> tuple[int | None, Iterable[Sequence]]:
        total = client.sequences.aggregate_count(
            filter=SequenceFilter(asset_subtree_ids=[{"externalId": root_asset_external_id}])
        )
        items = client.sequences(asset_subtree_external_ids=[root_asset_external_id])
        return total, items

    @classmethod
    def _from_file(cls, file_path: str | Path) -> tuple[int | None, Iterable[Sequence]]:
        sequences = SequenceList.load(Path(file_path).read_text())
        return len(sequences), sequences
