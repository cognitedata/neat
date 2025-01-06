import itertools
from collections.abc import Iterable
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Sequence, SequenceFilter

from cognite.neat._client.data_classes.neat_sequence import NeatSequence, NeatSequenceList

from ._base import ClassicCDFBaseExtractor, InstanceIdPrefix


class SequencesExtractor(ClassicCDFBaseExtractor[NeatSequence]):
    """Extract data from Cognite Data Fusions Sequences into Neat."""

    _default_rdf_type = "Sequence"
    _instance_id_prefix = InstanceIdPrefix.sequence

    @classmethod
    def _from_dataset(
        cls, client: CogniteClient, data_set_external_id: str
    ) -> tuple[int | None, Iterable[NeatSequence]]:
        total = client.sequences.aggregate_count(
            filter=SequenceFilter(data_set_ids=[{"externalId": data_set_external_id}])
        )
        items = client.sequences(data_set_external_ids=data_set_external_id)
        return total, cls._lookup_rows(items, client)

    @classmethod
    def _from_hierarchy(
        cls, client: CogniteClient, root_asset_external_id: str
    ) -> tuple[int | None, Iterable[NeatSequence]]:
        total = client.sequences.aggregate_count(
            filter=SequenceFilter(asset_subtree_ids=[{"externalId": root_asset_external_id}])
        )
        items = client.sequences(asset_subtree_external_ids=[root_asset_external_id])
        return total, cls._lookup_rows(items, client)

    @classmethod
    def _from_file(cls, file_path: str | Path) -> tuple[int | None, Iterable[NeatSequence]]:
        sequences = NeatSequenceList.load(Path(file_path).read_text())
        return len(sequences), sequences

    @classmethod
    def _lookup_rows(cls, sequence_iterable: Iterable[Sequence], client: CogniteClient) -> Iterable[NeatSequence]:
        iterator = iter(sequence_iterable)
        for sequences in iter(lambda: list(itertools.islice(iterator, client.config.max_workers)), []):
            # The PySDK uses max_workers to limit the number of requests made in parallel.
            # We can only get one set of sequence rows per request, so we chunk the sequences up into groups of
            # max_workers and then make a request to get all the rows for those sequences in one go.
            sequence_list = list(sequences)
            row_list = client.sequences.rows.retrieve(id=[seq.id for seq in sequence_list])
            rows_by_sequence_id = {row.id: row.rows for row in row_list}
            for seq in sequence_list:
                yield NeatSequence.from_cognite_sequence(seq, rows_by_sequence_id.get(seq.id))
