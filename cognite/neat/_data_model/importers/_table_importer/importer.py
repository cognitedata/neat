from collections.abc import Mapping
from typing import ClassVar, cast

from pydantic import ValidationError

from cognite.neat._data_model.importers._base import DMSImporter
from cognite.neat._data_model.models.dms import (
    RequestSchema,
)
from cognite.neat._exceptions import DataModelImportError
from cognite.neat._issues import ModelSyntaxError
from cognite.neat._utils.useful_types import CellValueType
from cognite.neat._utils.validation import as_json_path, humanize_validation_error

from .data_classes import TableDMS


class DMSTableImporter(DMSImporter):
    """Imports DMS from a table structure.

    The tables can are expected to be a dictionary where the keys are the table names and the values
    are lists of dictionaries representing the rows in the table.
    """

    # We can safely cast as we know the validation_alias is always set to a str.
    REQUIRED_SHEETS = tuple(
        cast(str, field_.validation_alias) for field_ in TableDMS.model_fields.values() if field_.is_required()
    )
    REQUIRED_SHEET_MESSAGES: ClassVar[Mapping[str, str]] = {
        f"Missing required column: {sheet!r}": f"Missing required sheet: {sheet!r}" for sheet in REQUIRED_SHEETS
    }

    def __init__(self, tables: dict[str, list[dict[str, CellValueType]]]) -> None:
        self._table = tables

    def to_data_model(self) -> RequestSchema:
        raise NotImplementedError()

    def _read_tables(self) -> TableDMS:
        try:
            # Check tables, columns, data type and entity syntax.
            table = TableDMS.model_validate(self._table)
        except ValidationError as e:
            errors = self._create_error_messages(e)
            raise DataModelImportError(errors) from None
        return table

    def _create_error_messages(self, error: ValidationError) -> list[ModelSyntaxError]:
        errors: list[ModelSyntaxError] = []
        seen: set[str] = set()
        for message in humanize_validation_error(
            error,
            humanize_location=self._location,
            field_name="column",
            missing_required_descriptor="missing",
        ):
            # Replace messages about missing required columns with missing required sheets.
            message = self.REQUIRED_SHEET_MESSAGES.get(message, message)
            if message in seen:
                # We treat all rows as the same, so we get duplicated errors for each row.
                continue
            seen.add(message)
            errors.append(ModelSyntaxError(message=message))
        return errors

    @staticmethod
    def _location(loc: tuple[str | int, ...]) -> str:
        if isinstance(loc[0], str) and len(loc) == 2:  # Sheet + row.
            # We skip the row as we treat all rows as the same. For example, if a required column is missing in one
            # row, it is missing in all rows.
            return f"{loc[0]} sheet"
        elif len(loc) == 3 and isinstance(loc[0], str) and isinstance(loc[1], int) and isinstance(loc[2], str):
            # This means there is something wrong in a specific cell.
            return f"{loc[0]} sheet row {loc[1] + 1} column {loc[2]!r}"
        # This should be unreachable as the TableDMS model only has 2 levels.
        return as_json_path(loc)
