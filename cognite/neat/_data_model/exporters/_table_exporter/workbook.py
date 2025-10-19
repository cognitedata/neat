import itertools
from collections.abc import Mapping
from typing import cast

from openpyxl import Workbook
from openpyxl.cell import MergedCell
from openpyxl.styles import Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

from cognite.neat._data_model.importers._table_importer.data_classes import DMSProperty, TableDMS
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
    # The following classes are used to refer to sheets and columns when creating the workbook.
    class Sheets:
        metadata = cast(str, TableDMS.model_fields["metadata"].validation_alias)
        properties = cast(str, TableDMS.model_fields["properties"].validation_alias)

    class PropertyColumns:
        view = cast(str, DMSProperty.model_fields["view"].validation_alias)
        view_property = cast(str, DMSProperty.model_fields["view_property"].validation_alias)
        connection = cast(str, DMSProperty.model_fields["connection"].validation_alias)
        value_type = cast(str, DMSProperty.model_fields["value_type"].validation_alias)
        min_count = cast(str, DMSProperty.model_fields["min_count"].validation_alias)
        max_count = cast(str, DMSProperty.model_fields["max_count"].validation_alias)
        default = cast(str, DMSProperty.model_fields["default"].validation_alias)
        auto_increment = cast(str, DMSProperty.model_fields["auto_increment"].validation_alias)
        container = cast(str, DMSProperty.model_fields["container"].validation_alias)
        container_property = cast(str, DMSProperty.model_fields["container_property"].validation_alias)
        container_property_name = cast(str, DMSProperty.model_fields["container_property_name"].validation_alias)
        container_property_description = cast(
            str, DMSProperty.model_fields["container_property_description"].validation_alias
        )
        index = cast(str, DMSProperty.model_fields["index"].validation_alias)
        constraint = cast(str, DMSProperty.model_fields["constraint"].validation_alias)

    def __init__(
        self,
        adjust_column_width: bool = True,
        style_headers: bool = True,
        row_band_highlighting: bool = True,
        separate_view_properties: bool = True,
        add_dropdowns: bool = True,
    ) -> None:
        self._adjust_column_width = adjust_column_width
        self._style_headers = style_headers
        self._row_band_highlighting = row_band_highlighting
        self._separate_view_properties = separate_view_properties
        self._add_dropdowns = add_dropdowns

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
            if self._style_headers:
                worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
                cell = worksheet.cell(row=1, column=1)
                cell.font = Font(bold=True, size=20)
                cell.fill = PatternFill(fgColor="FFC000", patternType="solid")

        worksheet.append(headers)
        header_row = 2 if main_header else 1
        if self._style_headers:
            for col_idx in range(1, len(headers) + 1):
                cell = worksheet.cell(row=header_row, column=col_idx)
                cell.font = Font(bold=True, size=14)
                cell.fill = PatternFill(fgColor="FFD966", patternType="solid")

        is_properties = worksheet.title == self.Sheets.properties
        fill_colors = itertools.cycle(["CADCFC", "FFFFFF"])
        fill_color = next(fill_colors)
        is_new_view = False
        last_view_value: CellValueType = None
        side = Side(style="thin")
        for row in table:
            if is_properties:
                is_new_view = row[self.PropertyColumns.view] != last_view_value and last_view_value is not None
            if is_new_view and is_properties and self._separate_view_properties:
                worksheet.append([None] * len(headers))  # Add an empty row between views
                if self._row_band_highlighting:
                    for cell in worksheet[worksheet.max_row]:
                        cell.border = Border(left=side, right=side, top=side, bottom=side)

            worksheet.append(list(row.values()))
            if self._row_band_highlighting and is_new_view and is_properties:
                fill_color = next(fill_colors)

            if self._row_band_highlighting and is_properties:
                for cell in worksheet[worksheet.max_row]:
                    cell.fill = PatternFill(fgColor=fill_color, fill_type="solid")
                    cell.border = Border(left=side, right=side, top=side, bottom=side)

            if is_properties:
                last_view_value = row[self.PropertyColumns.view]

        if self._style_headers:
            # openpyxl is not well typed
            worksheet.freeze_panes = worksheet.cell(row=header_row + 1, column=1)  # type: ignore[assignment]

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
