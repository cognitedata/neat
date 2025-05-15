import math
import typing
import urllib.parse
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from rdflib import RDF, URIRef

from cognite.neat.core._data_model.importers import SubclassInferenceImporter
from cognite.neat.core._data_model.models import UnverifiedConceptualDataModel
from cognite.neat.core._data_model.models import data_types as dt
from cognite.neat.core._data_model.models.conceptual import UnverifiedConceptualProperty
from cognite.neat.core._data_model.models.data_types import DataType
from cognite.neat.core._data_model.models.entities import (
    ConceptEntity,
    MultiValueTypeInfo,
    UnknownEntity,
    load_value_type,
)
from cognite.neat.core._issues import IssueList, NeatIssue
from cognite.neat.core._issues.errors import NeatValueError
from cognite.neat.core._store import NeatInstanceStore
from cognite.neat.core._utils.collection_ import iterate_progress_bar_if_above_config_threshold
from cognite.neat.core._utils.io_ import to_directory_compatible
from cognite.neat.core._utils.rdf_ import split_uri, uri_instance_to_display_name

from ._base import _END_OF_CLASS, _START_OF_CLASS, BaseLoader


class DictLoader(BaseLoader[dict[str, object]]):
    def __init__(
        self,
        graph_store: NeatInstanceStore,
        file_format: typing.Literal["parquet"] = "parquet",
        chunk_rows: int = 10_000,
    ) -> None:
        self.graph_store = graph_store
        self.file_format = file_format
        self.chunk_rows = chunk_rows
        self._inferred_properties_by_class: dict[str, list[UnverifiedConceptualProperty]] | None = None

    def _get_properties_by_class(self) -> dict[str, list[UnverifiedConceptualProperty]]:
        if self._inferred_properties_by_class is None:
            importer = SubclassInferenceImporter(
                IssueList(), self.graph_store.dataset, data_model_id=("neat_space", "TableSchema", "v1")
            )
            inferred_rules = importer.to_data_model()
            if inferred_rules.unverified_data_model is None:
                raise NeatValueError("Failed to infer schema for tables.")
            for prop in inferred_rules.unverified_data_model.properties:
                # Ensure that the value type is loaded.
                value_type = load_value_type(prop.value_type, inferred_rules.unverified_data_model.metadata.space)
                if isinstance(value_type, MultiValueTypeInfo):
                    value_type = self._convert_multi_value_type(value_type)
                prop.value_type = value_type

            self._inferred_properties_by_class = self._as_properties_by_class(inferred_rules.unverified_data_model)
        return self._inferred_properties_by_class

    @staticmethod
    def _convert_multi_value_type(multi_value_type: MultiValueTypeInfo) -> DataType | ConceptEntity:
        if all(isinstance(item, ConceptEntity) for item in multi_value_type.types):
            return dt.String()
        elif all(isinstance(item, DataType) for item in multi_value_type.types):
            if len(multi_value_type.types) == 2 and dt.String() in multi_value_type.types:
                # Use the more specific type if available
                return next(item for item in multi_value_type.types if item != dt.String())
            elif all(isinstance(item, dt.Double | dt.Long) for item in multi_value_type.types):
                return dt.Double()
            return dt.String()
        else:
            # Handle mixed types
            return dt.String()

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
        properties_by_class = self._get_properties_by_class()
        for result in self.graph_store.queries.select.list_types(remove_namespace=False):
            rdf_type = typing.cast(URIRef, result[0])
            namespace, entity_name = split_uri(rdf_type)
            display_name = urllib.parse.unquote(entity_name)
            properties_by_id = {prop.property_: prop for prop in properties_by_class.get(display_name, [])}
            if not properties_by_id:
                yield NeatValueError(f"No properties found for class: {display_name}")
                continue
            yield _START_OF_CLASS(display_name)
            total = self.graph_store.queries.select.count_of_type(rdf_type)
            iterable = self.graph_store.read(rdf_type)
            iterable = iterate_progress_bar_if_above_config_threshold(
                iterable, total, f"Loading {display_name} instances"
            )

            for instance_id, properties in iterable:
                identifier = uri_instance_to_display_name(instance_id)
                cleaned = self._clean_uris(properties, properties_by_id)
                cleaned["externalId"] = identifier
                yield cleaned
            yield _END_OF_CLASS

    def _clean_uris(
        self, properties: dict[str | URIRef, list], properties_by_id: dict[str, UnverifiedConceptualProperty]
    ) -> dict[str, object]:
        """Clean the URIs in the properties dictionary."""
        cleaned: dict[str, object] = {}
        for key, value in properties.items():
            if key == RDF.type:
                continue
            if isinstance(key, URIRef):
                key = uri_instance_to_display_name(key)
            value_ = (uri_instance_to_display_name(item) if isinstance(item, URIRef) else item for item in value)
            if prop := properties_by_id.get(key):
                value = [
                    item
                    for item in value_
                    if item
                    if self._is_matching_schema(item, typing.cast(DataType | ConceptEntity, prop.value_type))
                ]
            else:
                value = list(value_)

            if not value:
                continue
            if len(value) == 1:
                value = value[0]

            cleaned[key] = value
        return cleaned

    @staticmethod
    def _is_matching_schema(value: object, value_type: DataType | ConceptEntity) -> bool:
        if isinstance(value_type, ConceptEntity | UnknownEntity) and isinstance(value, str):
            return True
        elif isinstance(value_type, DataType):
            if isinstance(value_type, dt.Double) and isinstance(value, int):
                return True
            return isinstance(value, value_type.python)
        else:
            return False

    def _write_parquet_files(self, folder_path: Path) -> None:
        """Write the graph data to parquet files."""
        properties_by_class = self._get_properties_by_class()

        writer: pa.parquet.ParquetWriter | None = None
        schema: pa.Schema | None = None
        rows: list[dict[str, object]] = []
        try:
            for result in self._load():
                if (
                    isinstance(result, _START_OF_CLASS)
                    and result.conceptname is not None
                    and result.conceptname in properties_by_class
                ):
                    properties = properties_by_class[result.conceptname]
                    schema = self._create_schema(properties)
                    file_stem = to_directory_compatible(result.conceptname)
                    writer = pq.ParquetWriter(folder_path / f"{file_stem}.parquet", schema)
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
    def _as_properties_by_class(info: UnverifiedConceptualDataModel) -> dict[str, list[UnverifiedConceptualProperty]]:
        properties_by_class = defaultdict(list)
        for prop in info.properties:
            key = prop.concept if isinstance(prop.concept, str) else prop.concept.suffix
            properties_by_class[key].append(prop)
        return properties_by_class

    def _create_schema(self, properties: list[UnverifiedConceptualProperty]) -> pa.Schema:
        fields: list[pa.Field] = [pa.field("externalId", pa.string(), nullable=False)]
        for prop in properties:
            value_type = typing.cast(DataType | ConceptEntity | MultiValueTypeInfo | UnknownEntity, prop.value_type)
            pa_type = self._as_pa_type(value_type)
            if (isinstance(prop.max_count, float) and math.isinf(prop.max_count)) or (
                isinstance(prop.max_count, int) and prop.max_count > 1
            ):
                pa_type = pa.list_(pa_type)
            fields.append(pa.field(prop.property_, pa_type, nullable=True))

        return pa.schema(fields)

    @staticmethod
    def _as_pa_type(value_type: MultiValueTypeInfo | DataType | ConceptEntity | UnknownEntity) -> pa.DataType:
        if isinstance(value_type, MultiValueTypeInfo | ConceptEntity | UnknownEntity | dt.String):
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
            try:
                table = pa.Table.from_pylist(rows, schema=schema)
            except pa.ArrowTypeError as e:
                raise NeatValueError(f"Failed to convert {rows} to Arrow table: {e}") from e
            writer.write_table(table)

    @staticmethod
    def _close_writer(writer: pa.parquet.ParquetWriter | None) -> None:
        if writer is not None:
            writer.close()
