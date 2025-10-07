from pydantic import ValidationError

from cognite.neat._data_model.importers._base import DMSImporter
from cognite.neat._data_model.models.dms import (
    RequestSchema,
)
from cognite.neat._exceptions import ModelImportError
from cognite.neat._issues import ModelSyntaxError
from cognite.neat._utils.useful_types import CellValue
from cognite.neat._utils.validation import humanize_validation_error

from .data_classes import TableDMS


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
            errors = self._create_error_messages(e)
            raise ModelImportError(errors) from None

        if errors:
            raise ModelImportError(errors) from None
        return table

    def _create_error_messages(self, error: ValidationError) -> list[ModelSyntaxError]:
        errors: list[ModelSyntaxError] = []
        seen: set[str] = set()
        for message in humanize_validation_error(
            error,
            humanize_location=self._spreadsheet_location,
            field_name="column",
            missing_required="missing",
            field_renaming={"field": "sheet"},
        ):
            if message in seen:
                # We treat all rows as the same, so we get duplicated errors for each row.
                continue
            seen.add(message)
            errors.append(ModelSyntaxError(message=message))
        return errors

    @staticmethod
    def _spreadsheet_location(loc: tuple[str | int, ...]) -> str:
        if isinstance(loc[0], str) and len(loc) == 2:  # Sheet + row.
            return f"{loc[0]} sheet"
        if len(loc) == 3 and isinstance(loc[0], str) and isinstance(loc[1], int):  # Sheet + row + column.
            return f"in {loc[0]} sheet row {loc[1] + 1} column {loc[2]!r}"
        raise NotImplementedError()
