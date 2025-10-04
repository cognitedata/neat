from pydantic import ValidationError

from cognite.neat._data_model.importers._base import DMSImporter
from cognite.neat._data_model.models.dms import (
    ContainerPropertyDefinition,
    ContainerRequest,
    DataModelRequest,
    RequestSchema,
    SpaceRequest,
    ViewRequest,
)
from cognite.neat._utils.useful_types import CellValue

from .data_classes import DMSContainer, DMSProperty, DMSView, Metadata, TableDMS


class DMSTableImporter(DMSImporter):
    """Imports DMS from a table structure.

    The tables can are expected to be a dictionary where the keys are the table names and the values
    are lists of dictionaries representing the rows in the table.
    """

    def __init__(self, tables: dict[str, list[dict[str, CellValue]]]) -> None:
        self._table = tables

    def to_data_model(self) -> RequestSchema:
        try:
            # Check tables and columns are correct.
            table = TableDMS.model_validate(self._table)
        except ValidationError:
            raise NotImplementedError("Error handling is not yet implemented.") from None

        default_space, default_version = self._get_defaults(table.metadata)

        data_model = self._read_data_model(table.metadata)
        views = self._read_views(table.views, default_space, default_version)
        containers = self._read_containers(table.containers, default_space)
        self._populate_properties(views, containers, table.properties, default_space, default_version)

        try:
            return RequestSchema.model_validate(
                {
                    "dataModel": data_model.model_dump(exclude_unset=True),
                    "views": {view.as_reference(): view for view in views},
                    "containers": {container.as_reference(): container for container in containers},
                    "spaces": {default_space: SpaceRequest(space=default_space)},
                }
            )
        except ValidationError as e:
            # Error handling is not yet implemented.
            raise NotImplementedError("Could not create RequestSchema from the provided data.") from e

    def _get_defaults(self, metadata: list[Metadata]) -> tuple[str, str]:
        # Implementation to extract default space and version from metadata
        pass

    def _read_data_model(self, metadata: list[Metadata]) -> DataModelRequest:
        # Implementation to read data model from metadata
        pass

    def _read_views(self, views: list[DMSView], default_space: str, default_version: str) -> list[ViewRequest]:
        # Implementation to read views from DMSView list
        pass

    def _read_containers(self, containers: list[DMSContainer], default_space: str) -> list[ContainerRequest]:
        # Implementation to read containers from DMSContainer list
        pass

    def _create_container_property(self, prop: DMSProperty) -> ContainerPropertyDefinition:
        raise NotImplementedError()

    def _populate_properties(
        self,
        views: list[ViewRequest],
        containers: list[ContainerRequest],
        properties: list[DMSProperty],
        default_space: str,
        default_version: str,
    ) -> None:
        raise NotImplementedError()
