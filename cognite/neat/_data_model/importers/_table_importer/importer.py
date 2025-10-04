from pydantic import ValidationError

from cognite.neat._data_model.importers._base import DMSImporter
from cognite.neat._data_model.models.dms import (
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelRequest,
    RequestSchema,
    SpaceRequest,
    ViewReference,
    ViewRequest,
    ViewRequestProperty,
)
from cognite.neat._exceptions import ModelImportError
from cognite.neat._issues import ModelSyntaxError
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.useful_types import CellValue
from cognite.neat._utils.validation import humanize_validation_error

from .data_classes import DMSContainer, DMSProperty, DMSView, TableDMS


class DMSTableImporter(DMSImporter):
    """Imports DMS from a table structure.

    The tables can are expected to be a dictionary where the keys are the table names and the values
    are lists of dictionaries representing the rows in the table.
    """

    def __init__(self, tables: dict[str, list[dict[str, CellValue]]]) -> None:
        self._table = tables
        self._errors: list[ModelSyntaxError] = []

    def to_data_model(self) -> RequestSchema:
        table = self._read_tables()

        metadata_kv = {meta.name: meta.value for meta in table.metadata}
        default_space, default_version = metadata_kv.get("space"), metadata_kv.get("version")
        if default_space is None or default_version is None:
            missing = {"space" if default_space is None else "", "version" if default_version is None else ""}
            self._errors.append(
                ModelSyntaxError(message=f"Missing required metadata fields: {humanize_collection(missing)}")
            )
            raise ModelImportError(self._errors) from None
        space, version = str(default_space), str(default_version)
        container_properties, view_properties = self._read_properties(table.properties, space, version)
        containers = self._read_containers(table.containers, space, container_properties)
        views = self._read_views(table.views, space, version, view_properties)

        data_model = self._read_data_model(
            metadata_kv,
            [
                view.as_reference()
                for view, table in zip(views, table.views, strict=False)
                if table.in_model is not False
            ],
        )
        if self._errors:
            raise ModelImportError(self._errors) from None

        try:
            return RequestSchema.model_validate(
                {
                    "dataModel": data_model.model_dump(exclude_unset=True, by_alias=True),
                    "views": [view.model_dump(by_alias=True) for view in views],
                    "containers": [container.model_dump(by_alias=True) for container in containers],
                    "spaces": [SpaceRequest(space=space).model_dump(by_alias=True)],
                }
            )
        except ValidationError as e:
            self._errors.extend([ModelSyntaxError(message=message) for message in humanize_validation_error(e)])
            raise ModelImportError(self._errors) from None

    def _read_tables(self) -> TableDMS:
        try:
            # Check tables and columns are correct.
            table = TableDMS.model_validate(self._table)
        except ValidationError as e:
            self._errors.extend([ModelSyntaxError(message=message) for message in humanize_validation_error(e)])
            raise ModelImportError(self._errors) from None
        unused_tables = set(self._table.keys()) - {
            field_.alias or table_id for table_id, field_ in TableDMS.model_fields.items()
        }
        if unused_tables:
            self._errors.append(ModelSyntaxError(message=f"Unused tables found: {humanize_collection(unused_tables)}"))
        return table

    def _read_properties(
        self,
        properties: list[DMSProperty],
        default_space: str,
        default_version: str,
    ) -> tuple[
        dict[ContainerReference, dict[str, ContainerPropertyDefinition]],
        dict[ViewReference, dict[str, ViewRequestProperty]],
    ]:
        raise NotImplementedError()

    def _read_containers(
        self,
        containers: list[DMSContainer],
        default_space: str,
        properties: dict[ContainerReference, dict[str, ContainerPropertyDefinition]],
    ) -> list[ContainerRequest]:
        # Implementation to read containers from DMSContainer list
        raise NotImplementedError()

    def _read_views(
        self,
        views: list[DMSView],
        default_space: str,
        default_version: str,
        properties: dict[ViewReference, dict[str, ViewRequestProperty]],
    ) -> list[ViewRequest]:
        # Implementation to read views from DMSView list
        raise NotImplementedError()

    @staticmethod
    def _read_data_model(metadata: dict[str, CellValue], views: list[ViewReference]) -> DataModelRequest:
        return DataModelRequest.model_construct(**metadata, views=views)  # type: ignore[arg-type]
