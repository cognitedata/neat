import math
import typing
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from rdflib import RDF, URIRef

from cognite.neat.core._issues import IssueList, NeatIssue
from cognite.neat.core._issues.errors import NeatValueError
from cognite.neat.core._rules.importers import SubclassInferenceImporter
from cognite.neat.core._rules.models import InformationInputRules
from cognite.neat.core._rules.models import data_types as dt
from cognite.neat.core._rules.models.data_types import DataType
from cognite.neat.core._rules.models.entities import ClassEntity, MultiValueTypeInfo, UnknownEntity, load_value_type
from cognite.neat.core._rules.models.information import InformationInputProperty
from cognite.neat.core._store import NeatGraphStore
from cognite.neat.core._utils.collection_ import iterate_progress_bar_if_above_config_threshold
from cognite.neat.core._utils.io_ import to_directory_compatible
from cognite.neat.core._utils.rdf_ import split_uri, uri_instance_to_display_name

from ._base import _END_OF_CLASS, _START_OF_CLASS, BaseLoader


class DictLoader(BaseLoader[dict[str, object]]):
    def __init__(
        self, graph_store: NeatGraphStore, file_format: typing.Literal["parquet"] = "parquet", chunk_rows: int = 10_000
    ) -> None:
        self.graph_store = graph_store
        self.file_format = file_format
        self.chunk_rows = chunk_rows

    def write_to_file(self, filepath: Path) -> None:
        if self.file_format != "parquet":
            raise NeatValueError(f"Unsupported file format: {self.file_format!r}. Only 'parquet' is supported.")
        if not filepath.exists() and filepath.suffix == "":
            filepath.mkdir(parents=True, exist_ok=True)
        if not filepath.is_dir():
            raise NeatValueError(f"Expected a directory, but got a file: {filepath.as_posix()!r}.")
        self._write_parquet_files(filepath)

    def _load(
        self, stop_on_exception: bool = False
    ) -> Iterable[dict[str, object] | NeatIssue | type[_END_OF_CLASS] | _START_OF_CLASS]:
        for result in self.graph_store.queries.select.list_types(remove_namespace=False):
            rdf_type = typing.cast(URIRef, result[0])
            display_name = uri_instance_to_display_name(rdf_type)
            yield _START_OF_CLASS(display_name)
            for instance_id, properties in self.graph_store.read(rdf_type):
                identifier = uri_instance_to_display_name(instance_id)
                cleaned = self._clean_uris(properties)
                cleaned["external_id"] = identifier
                yield cleaned
            yield _END_OF_CLASS

    @staticmethod
    def _clean_uris(properties: dict[str | URIRef, list]) -> dict[str, object]:
        """Clean the URIs in the properties dictionary."""
        cleaned: dict[str, object] = {}
        for key, value in properties.items():
            if key == RDF.type:
                continue
            if isinstance(key, URIRef):
                key = uri_instance_to_display_name(key)
            value = [uri_instance_to_display_name(item) if isinstance(item, URIRef) else item for item in value]
            if len(value) == 1:
                value = value[0]
            cleaned[key] = value
        return cleaned

    def _write_parquet_files(self, folder_path: Path) -> None:
        """Write the graph data to parquet files."""
        importer = SubclassInferenceImporter(
            IssueList(), self.graph_store.dataset, data_model_id=("neat_space", "TableSchema", "v1")
        )
        inferred_rules = importer.to_rules()
        if inferred_rules.rules is None:
            raise NeatValueError("Failed to infer schema for tables.")
        info = inferred_rules.rules
        properties_by_class = self._as_properties_by_class(info)

        writer: pa.parquet.ParquetWriter | None = None
        schema: pa.Schema | None = None
        rows: list[dict[str, object]] = []
        try:
            for result in self._load():
                if (
                    isinstance(result, _START_OF_CLASS)
                    and result.class_name is not None
                    and result.class_name in properties_by_class
                ):
                    properties = properties_by_class[result.class_name]
                    schema = self._create_schema(properties, info.metadata.space)
                    writer = pq.ParquetWriter(folder_path / f"{result.class_name}.parquet", schema)
                elif result is _END_OF_CLASS:
                    self._write_rows(writer, schema, rows)
                    self._close_writer(writer)
                    writer = None
                    schema = None
                elif isinstance(result, dict):
                    rows.append(result)
                if len(rows) >= self.chunk_rows:
                    self._write_rows(writer, schema, rows)
                    rows.clear()
        finally:
            self._write_rows(writer, schema, rows)
            self._close_writer(writer)

    @staticmethod
    def _as_properties_by_class(info: InformationInputRules) -> dict[str, list[InformationInputProperty]]:
        properties_by_class = defaultdict(list)
        for prop in info.properties:
            key = prop.class_ if isinstance(prop.class_, str) else prop.class_.suffix
            properties_by_class[key].append(prop)
        return properties_by_class

    def _create_schema(self, properties: list[InformationInputProperty], default_prefix: str) -> pa.Schema:
        fields: list[pa.Field] = []
        for prop in properties:
            value_type = load_value_type(prop.value_type, default_prefix)
            pa_type = self._as_pa_type(value_type)
            if (isinstance(prop.max_count, float) and math.isinf(prop.max_count)) or (
                isinstance(prop.max_count, int) and prop.max_count > 1
            ):
                pa_type = pa.list_(pa_type)
            fields.append(pa.field(prop.property_, pa_type, nullable=True))

        return pa.schema(fields)

    @staticmethod
    def _as_pa_type(value_type: MultiValueTypeInfo | DataType | ClassEntity | UnknownEntity) -> pa.DataType:
        if isinstance(value_type, MultiValueTypeInfo | ClassEntity | UnknownEntity | dt.String):
            return pa.string()
        elif isinstance(value_type, dt.Long | dt.Integer | dt.NonPositiveInteger):
            return pa.int64()
        elif isinstance(value_type, dt.Float | dt.Double):
            return pa.float64()
        elif isinstance(value_type, dt.Boolean):
            return pa.bool_()
        elif isinstance(value_type, dt.DateTime):
            return pa.timestamp("ms", tz="UTC")
        elif isinstance(value_type, dt.Date):
            return pa.date32()
        else:
            raise NeatValueError(f"Unsupported value type: {value_type!r}")

    @staticmethod
    def _write_rows(
        writer: pa.parquet.ParquetWriter | None, schema: pa.Schema | None, rows: list[dict[str, object]]
    ) -> None:
        if writer is not None and schema is not None:
            table = pa.Table.from_pylist(rows, schema=schema)
            writer.write_table(table)

    @staticmethod
    def _close_writer(writer: pa.parquet.ParquetWriter | None) -> None:
        if writer is not None:
            writer.close()
