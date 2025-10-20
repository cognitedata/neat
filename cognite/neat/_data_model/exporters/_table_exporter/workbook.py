import itertools
from collections.abc import Mapping, Set
from typing import Literal, cast

from openpyxl import Workbook
from openpyxl.cell import MergedCell
from openpyxl.styles import Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

from cognite.neat._data_model._constants import (
    CDF_CDM_SPACE,
    COGNITE_CONCEPTS_3D,
    COGNITE_CONCEPTS_ANNOTATIONS,
    COGNITE_CONCEPTS_CONFIGURATIONS,
    COGNITE_CONCEPTS_INTERFACES,
    COGNITE_CONCEPTS_MAIN,
    CDF_CORE_v1,
)
from cognite.neat._data_model.importers._table_importer.data_classes import DMSContainer, DMSProperty, DMSView, TableDMS
from cognite.neat._data_model.models.dms import (
    DMS_DATA_TYPES,
    EnumProperty,
    FileCDFExternalIdReference,
    SequenceCDFExternalIdReference,
    TimeseriesCDFExternalIdReference,
)
from cognite.neat._utils.useful_types import CellValueType, DataModelTableType

MAIN_HEADERS_BY_SHEET_NAME: Mapping[str, str] = {
    "Properties": "Definition of Properties",
    "Views": "Definition of Views",
    "Containers": "Definition of Containers",
    "Nodes": "Definition of Nodes",
    "Enum": "Definition of Enum Collections",
}
MAX_COLUMN_WIDTH = 70.0
DROPDOWN_SOURCE_SHEET_NAME = "_dropdown_source"
HEADER_ROWS = 2


class WorkbookCreator:
    # The following classes are used to refer to sheets and columns when creating the workbook.
    class Sheets:
        metadata = cast(str, TableDMS.model_fields["metadata"].validation_alias)
        properties = cast(str, TableDMS.model_fields["properties"].validation_alias)
        view = cast(str, TableDMS.model_fields["views"].validation_alias)
        containers = cast(str, TableDMS.model_fields["containers"].validation_alias)
        enum = cast(str, TableDMS.model_fields["enum"].validation_alias)
        nodes = cast(str, TableDMS.model_fields["nodes"].validation_alias)

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

    class ContainerColumns:
        container = cast(str, DMSContainer.model_fields["container"].validation_alias)
        used_for = cast(str, DMSContainer.model_fields["used_for"].validation_alias)

    class ViewColumns:
        view = cast(str, DMSView.model_fields["view"].validation_alias)
        implements = cast(str, DMSView.model_fields["implements"].validation_alias)

    class DropdownSourceColumns:
        view = 1
        implements = 2
        value_type = 3
        container = 4
        in_model = 5
        immutable = 5
        used_for = 6

    def __init__(
        self,
        adjust_column_width: bool = True,
        style_headers: bool = True,
        row_band_highlighting: bool = True,
        separate_view_properties: bool = True,
        add_dropdowns: bool = True,
        dropdown_implements: Set[Literal["main", "interface", "configuration", "annotation", "3D"]] = frozenset(
            {"main", "interface"}
        ),
        max_views: int = 100,
        max_containers: int = 100,
    ) -> None:
        self._adjust_column_width = adjust_column_width
        self._style_headers = style_headers
        self._row_band_highlighting = row_band_highlighting
        self._separate_view_properties = separate_view_properties
        self._add_dropdowns = add_dropdowns
        self._dropdown_implements = dropdown_implements
        self._max_views = max_views
        self._max_containers = max_containers

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
                self._write_table_to_worksheet(worksheet, table, MAIN_HEADERS_BY_SHEET_NAME[sheet_name])
            if self._adjust_column_width:
                self._adjust_column_widths(worksheet)
        if self._add_dropdowns:
            self._add_drop_downs(workbook)
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
        worksheet.append([main_header] + [""] * (len(headers) - 1))
        if self._style_headers:
            worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(3, len(headers)))
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

        self._write_rows_to_worksheet(worksheet, table, headers)

        if self._style_headers:
            # openpyxl is not well typed
            worksheet.freeze_panes = worksheet.cell(row=header_row + 1, column=1)  # type: ignore[assignment]

    def _write_rows_to_worksheet(
        self, worksheet: Worksheet, table: list[dict[str, CellValueType]], headers: list[str]
    ) -> None:
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

    def _add_drop_downs(self, workbook: Workbook) -> None:
        """Adds drop down menus to specific columns for fast and accurate data entry

        Args:
            workbook: Workbook representation of the Excel file.

        !!! note "Why defining individual data validation per desired column?
            This is due to the internal working of openpyxl. Adding same validation to
            different column leads to unexpected behavior when the openpyxl workbook is exported
            as and Excel file. Probably, the validation is not copied to the new column,
            but instead reference to the data validation object is added.
        """

        self._create_dropdown_source_sheet(workbook)

    def _create_dropdown_source_sheet(self, workbook: Workbook) -> None:
        """This methods creates a hidden sheet in the workbook which contains
        the source data for the drop-down menus.

        Args:
            workbook: Workbook representation of the Excel file.

        """

        dropdown_sheet = workbook.create_sheet(title=DROPDOWN_SOURCE_SHEET_NAME)

        # skip types which require special handling (enum) or are surpassed by CDM (CDF references)
        exclude = {
            # MyPy does not understand that model_fields is in all pydantic classes.
            prop.model_fields["type"].default  # type: ignore[attr-defined]
            for prop in [
                EnumProperty,
                TimeseriesCDFExternalIdReference,
                SequenceCDFExternalIdReference,
                FileCDFExternalIdReference,
            ]
        }
        for no, dms_type in enumerate([type for type in DMS_DATA_TYPES.keys() if type not in exclude], 1):
            dropdown_sheet.cell(row=no, column=self.DropdownSourceColumns.value_type, value=dms_type)

        cognite_concepts = self._get_cognite_concepts()

        for i, concept in enumerate(cognite_concepts, 1):
            dropdown_sheet.cell(
                row=i,
                column=self.DropdownSourceColumns.implements,
                value=f"{CDF_CDM_SPACE}:{concept}(version={CDF_CORE_v1})",
            )

        dms_type_count = len(DMS_DATA_TYPES) - len(exclude)
        core_concept_count = len(cognite_concepts)
        for i in range(1, self._max_views + 1):
            source_row = i + HEADER_ROWS
            view_reference = f'=IF(ISBLANK({self.Sheets.view}!A{source_row}), "", {self.Sheets.view}!A{source_row})'
            dropdown_sheet.cell(row=i, column=self.DropdownSourceColumns.view, value=view_reference)
            dropdown_sheet.cell(
                row=i + core_concept_count, column=self.DropdownSourceColumns.implements, value=view_reference
            )
            dropdown_sheet.cell(
                row=i + dms_type_count, column=self.DropdownSourceColumns.value_type, value=view_reference
            )

        for i in range(1, self._max_containers + 1):
            source_row = i + HEADER_ROWS
            container_reference = (
                f'=IF(ISBLANK({self.Sheets.containers}!A{source_row}), "", {self.Sheets.containers}!A{source_row})'
            )
            dropdown_sheet.cell(row=i, column=self.DropdownSourceColumns.container, value=container_reference)

        for i, value in enumerate([True, False, None], 1):
            dropdown_sheet.cell(row=i, column=self.DropdownSourceColumns.in_model, value=value)

        for i, value in enumerate(["node", "edge", "all"], 1):
            dropdown_sheet.cell(row=i, column=self.DropdownSourceColumns.used_for, value=value)

        dropdown_sheet.sheet_state = "hidden"

    def _get_cognite_concepts(self) -> list[str]:
        """Gets the cognite concepts based on the dropdown_implements setting."""
        cognite_concepts: list[str] = []
        if self._dropdown_implements:
            if "main" in self._dropdown_implements:
                cognite_concepts.extend(COGNITE_CONCEPTS_MAIN)
            if "interface" in self._dropdown_implements:
                cognite_concepts.extend(COGNITE_CONCEPTS_INTERFACES)
            if "configuration" in self._dropdown_implements:
                cognite_concepts.extend(COGNITE_CONCEPTS_CONFIGURATIONS)
            if "annotation" in self._dropdown_implements:
                cognite_concepts.extend(COGNITE_CONCEPTS_ANNOTATIONS)
            if "3D" in self._dropdown_implements:
                cognite_concepts.extend(COGNITE_CONCEPTS_3D)
        return cognite_concepts
