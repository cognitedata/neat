import itertools
import json
import typing
from collections.abc import Iterable, Set
from pathlib import Path
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes import Sequence, SequenceFilter
from rdflib import RDF, XSD, Literal, Namespace, URIRef
from typing_extensions import Self

from cognite.neat.v0.core._client.data_classes.neat_sequence import (
    NeatSequence,
    NeatSequenceList,
)
from cognite.neat.v0.core._shared import Triple

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix


class SequencesExtractor(ClassicCDFBaseExtractor[NeatSequence]):
    """Extract data from Cognite Data Fusions Sequences into Neat.

    Args:
        items (Iterable[T_CogniteResource]): An iterable of classic resource.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        total (int, optional): The total number of items to load. If passed, you will get a progress bar if rich
            is installed. Defaults to None.
        limit (int, optional): The maximal number of items to load. Defaults to None. This is typically used for
            testing setup of the extractor. For example, if you are extracting 100 000 assets, you might want to
            limit the extraction to 1000 assets to test the setup.
        unpack_metadata (bool, optional): Whether to unpack metadata. Defaults to False, which yields the metadata as
            a JSON string.
        skip_metadata_values (set[str] | frozenset[str] | None, optional): If you are unpacking metadata, then
           values in this set will be skipped.
        camel_case (bool, optional): Whether to use camelCase instead of snake_case for property names.
            Defaults to True.
        as_write (bool, optional): Whether to use the write/request format of the items. Defaults to False.
        unpack_columns (bool, optional): Whether to unpack columns. Defaults to False.
    """

    _default_rdf_type = "Sequence"
    _column_rdf_type = "ColumnClass"
    _instance_id_prefix = InstanceIdPrefix.sequence

    def __init__(
        self,
        items: Iterable[NeatSequence],
        namespace: Namespace | None = None,
        total: int | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
        camel_case: bool = True,
        as_write: bool = False,
        prefix: str | None = None,
        identifier: typing.Literal["id", "externalId"] = "id",
        unpack_columns: bool = False,
        skip_connections: bool = False,
    ):
        super().__init__(
            items,
            namespace,
            total,
            limit,
            unpack_metadata,
            skip_metadata_values,
            camel_case,
            as_write,
            prefix,
            identifier,
            skip_connections,
        )
        self.unpack_columns = unpack_columns

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
        camel_case: bool = True,
        as_write: bool = False,
        prefix: str | None = None,
        identifier: typing.Literal["id", "externalId"] = "id",
        unpack_columns: bool = False,
        skip_rows: bool = False,
    ) -> Self:
        total, items = cls._handle_no_access(lambda: cls._from_dataset(client, data_set_external_id, skip_rows))
        return cls(
            items,
            namespace,
            total,
            limit,
            unpack_metadata,
            skip_metadata_values,
            camel_case,
            as_write,
            prefix,
            identifier,
            unpack_columns,
        )

    @classmethod
    def from_hierarchy(
        cls,
        client: CogniteClient,
        root_asset_external_id: str,
        namespace: Namespace | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
        camel_case: bool = True,
        as_write: bool = False,
        prefix: str | None = None,
        identifier: typing.Literal["id", "externalId"] = "id",
        unpack_columns: bool = False,
        skip_rows: bool = False,
    ) -> ClassicCDFBaseExtractor:
        total, items = cls._handle_no_access(lambda: cls._from_hierarchy(client, root_asset_external_id, skip_rows))
        return cls(
            items,
            namespace,
            total,
            limit,
            unpack_metadata,
            skip_metadata_values,
            camel_case,
            as_write,
            prefix,
            identifier,
            unpack_columns,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str | Path,
        namespace: Namespace | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
        camel_case: bool = True,
        as_write: bool = False,
        prefix: str | None = None,
        identifier: typing.Literal["id", "externalId"] = "id",
        unpack_columns: bool = False,
    ) -> ClassicCDFBaseExtractor:
        total, items = cls._from_file(file_path)
        return cls(
            items,
            namespace,
            total,
            limit,
            unpack_metadata,
            skip_metadata_values,
            camel_case,
            as_write,
            prefix,
            identifier,
            unpack_columns,
        )

    @classmethod
    def _from_dataset(
        cls, client: CogniteClient, data_set_external_id: str, skip_rows: bool = False
    ) -> tuple[int | None, Iterable[NeatSequence]]:
        total = client.sequences.aggregate_count(
            filter=SequenceFilter(data_set_ids=[{"externalId": data_set_external_id}])
        )
        items = client.sequences(data_set_external_ids=data_set_external_id)
        if skip_rows:
            return total, (NeatSequence.from_cognite_sequence(seq) for seq in items)
        else:
            return total, cls._lookup_rows(items, client)

    @classmethod
    def _from_hierarchy(
        cls, client: CogniteClient, root_asset_external_id: str, skip_rows: bool = False
    ) -> tuple[int | None, Iterable[NeatSequence]]:
        total = client.sequences.aggregate_count(
            filter=SequenceFilter(asset_subtree_ids=[{"externalId": root_asset_external_id}])
        )
        items = client.sequences(asset_subtree_external_ids=[root_asset_external_id])
        if skip_rows:
            return total, (NeatSequence.from_cognite_sequence(seq) for seq in items)
        else:
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

    def _item2triples_special_cases(self, id_: URIRef, dumped: dict[str, Any]) -> list[Triple]:
        """For sequences, columns and rows are special cases.'"""
        if self.unpack_columns:
            return self._unpack_columns(id_, dumped)
        else:
            return self._default_columns_and_rows(id_, dumped)

    def _default_columns_and_rows(self, id_: URIRef, dumped: dict[str, Any]) -> list[Triple]:
        triples: list[Triple] = []
        if "columns" in dumped:
            columns = dumped.pop("columns")
            triples.extend(
                [
                    (
                        id_,
                        self.namespace.columns,
                        # Rows have a rowNumber, so we introduce colNumber here to be consistent.
                        Literal(json.dumps({"colNumber": no, **col}), datatype=XSD._NS["json"]),
                    )
                    for no, col in enumerate(columns, 1)
                ]
            )
        if "rows" in dumped:
            rows = dumped.pop("rows")
            triples.extend(
                [(id_, self.namespace.rows, Literal(json.dumps(row), datatype=XSD._NS["json"])) for row in rows]
            )
        return triples

    def _unpack_columns(self, id_: URIRef, dumped: dict[str, Any]) -> list[Triple]:
        triples: list[Triple] = []
        columnValueTypes: list[str] = []
        column_order: list[str] = []
        if columns := dumped.pop("columns", None):
            for col in columns:
                external_id = col.pop("externalId")
                column_order.append(external_id)
                value_type = col.pop("valueType")
                columnValueTypes.append(value_type)

                col_id = self.namespace[f"Column_{external_id}"]
                triples.append((id_, self.namespace[external_id], col_id))
                type_ = self.namespace[self._column_rdf_type]
                triples.append((col_id, RDF.type, type_))
                if metadata := col.pop("metadata", None):
                    triples.extend(self._metadata_to_triples(col_id, metadata))
                # Should only be name and description left in col
                for key, value in col.items():
                    if value is None:
                        continue
                    triples.append((col_id, self.namespace[key], Literal(value, datatype=XSD.string)))

            triples.append(
                (id_, self.namespace.columnOrder, Literal(json.dumps(column_order), datatype=XSD._NS["json"]))
            )
            triples.append(
                (id_, self.namespace.columnValueTypes, Literal(json.dumps(columnValueTypes), datatype=XSD._NS["json"]))
            )
        if rows := dumped.pop("rows", None):
            values_by_column: list[list[Any]] = [[] for _ in column_order]
            for row in rows:
                for i, value in enumerate(row["values"]):
                    values_by_column[i].append(value)
            for col_name, values in zip(column_order, values_by_column, strict=False):
                triples.append(
                    (id_, self.namespace[f"{col_name}Values"], Literal(json.dumps(values), datatype=XSD._NS["json"]))
                )

        return triples
