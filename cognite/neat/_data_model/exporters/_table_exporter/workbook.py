from collections.abc import Mapping
from typing import cast

from openpyxl import Workbook
from openpyxl.cell import MergedCell
from openpyxl.worksheet.worksheet import Worksheet

from cognite.neat._data_model.importers._table_importer.data_classes import TableDMS
from cognite.neat._utils.useful_types import CellValueType, DataModelTableType

MAIN_HEADERS_BY_SHEET_NAME: Mapping[str, str] = {
    "Properties": "Definition of Properties",
    "Views": "Definition of Views",
    "Containers": "Definition of Containers",
    "Nodes": "Definition of Nodes",
    "Enum": "Definition of Enum Collections",
}
MAX_COLUMN_WIDTH = 70.0


class WorkbookCreator:
    # The following is used to get the sheet names from the TableDMS dataclass
    class Sheets:
        metadata = cast(str, TableDMS.model_fields["metadata"].validation_alias)

    def __init__(self, adjust_column_width: bool = True, add_dropdowns: bool = True) -> None:
        self._add_dropdowns = add_dropdowns
        self._adjust_column_width = adjust_column_width

    def create_workbook(self, tables: DataModelTableType) -> Workbook:
        """Creates an Excel workbook from the data model.

        Args:
            tables (DataModelTableType): The data model in table
        """
        workbook = Workbook()
        # Remove default sheet named "Sheet"
        workbook.remove(workbook["Sheet"])

        for sheet_name, table in tables.items():
            if not table and sheet_name not in TableDMS.required_sheets():
                continue
            worksheet = workbook.create_sheet(title=sheet_name)
            if sheet_name == self.Sheets.metadata:
                self._write_metadata_to_worksheet(worksheet, table)
            else:
                self._write_table_to_worksheet(worksheet, table, MAIN_HEADERS_BY_SHEET_NAME.get(sheet_name, ""))
            if self._adjust_column_width:
                self._adjust_column_widths(worksheet)
        return workbook

    def _write_metadata_to_worksheet(self, worksheet: Worksheet, table: list[dict[str, CellValueType]]) -> None:
        """Writes Metadata to the given worksheet.

        Metadata is written as key-value pairs without headers.
        """
        for row in table:
            worksheet.append(list(row.values()))

    def _write_table_to_worksheet(
        self, worksheet: Worksheet, table: list[dict[str, CellValueType]], main_header: str
    ) -> None:
        headers = list(table[0].keys())
        if main_header:
            worksheet.append([main_header] + [""] * (len(headers) - 1))

        worksheet.append(headers)
        for row in table:
            worksheet.append(list(row.values()))

    @classmethod
    def _adjust_column_widths(cls, worksheet: Worksheet) -> None:
        for column_cells in worksheet.columns:
            try:
                max_length = max(len(str(cell.value)) for cell in column_cells if cell.value is not None)
            except ValueError:
                max_length = 0

            selected_column = column_cells[0]
            if isinstance(selected_column, MergedCell):
                selected_column = column_cells[1]

            current = worksheet.column_dimensions[selected_column.column_letter].width or (max_length + 0.5)  # type: ignore[union-attr]
            worksheet.column_dimensions[selected_column.column_letter].width = min(  # type: ignore[union-attr]
                max(current, max_length + 0.5), MAX_COLUMN_WIDTH
            )
        return None
