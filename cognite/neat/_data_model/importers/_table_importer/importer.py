from pydantic import ValidationError

from cognite.neat._data_model.importers._base import DMSImporter
from cognite.neat._data_model.models.dms import (
    RequestSchema,
)
from cognite.neat._exceptions import ModelImportError
from cognite.neat._issues import ModelSyntaxError
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.useful_types import CellValue
from cognite.neat._utils.validation import humanize_validation_error

from .data_classes import MetadataValue, TableDMS


class DMSTableImporter(DMSImporter):
    """Imports DMS from a table structure.

    The tables can are expected to be a dictionary where the keys are the table names and the values
    are lists of dictionaries representing the rows in the table.
    """

    def __init__(self, tables: dict[str, list[dict[str, CellValue]]]) -> None:
        self._table = tables

    def to_data_model(self) -> RequestSchema:
        raise NotImplementedError()

    def _read_tables(self) -> TableDMS:
        errors: list[ModelSyntaxError] = []
        try:
            # Check tables, columns, data type and entity syntax.
            table = TableDMS.model_validate(self._table)
        except ValidationError as e:
            errors.extend([ModelSyntaxError(message=message) for message in humanize_validation_error(e)])
            raise ModelImportError(errors) from None

        if errors:
            raise ModelImportError(errors) from None
        return table

    @staticmethod
    def _read_defaults(metadata: list[MetadataValue]) -> tuple[str, str]:
        """Reads the space and version from the metadata table."""
        default_space: str | None = None
        default_version: str | None = None
        missing = {"space", "version"}
        for meta in metadata:
            if meta.name == "space":
                default_space = str(meta.value)
                missing.remove("space")
            elif meta.name == "version":
                default_version = str(meta.value)
                missing.remove("version")
        if missing:
            error = ModelSyntaxError(message=f"In Metadata missing required values: {humanize_collection(missing)}")
            # If space or version is missing, we cannot continue parsing the model as these are used as defaults.
            raise ModelImportError([error]) from None
        return str(default_space), str(default_version)
