from __future__ import annotations

import itertools
from pathlib import Path
from types import GenericAlias
from typing import Any, ClassVar, Literal, get_args

from openpyxl import Workbook
from openpyxl.cell import MergedCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from cognite.neat.rules._shared import Rules
from cognite.neat.rules.models._rules.base import RoleTypes, SheetEntity

from ._base import BaseExporter


class ExcelExporter(BaseExporter[Workbook]):
    """Export rules to Excel.

    Args:
        styling: The styling to use for the Excel file. Defaults to "default". See below for details
            on the different styles.
        output_role: The role to use for the exported spreadsheet. If provided, the rules will be converted to
            this role formate before being written to excel. If not provided, the role from the rules will be used.

    The following styles are available:

    - "none":    No styling is applied.
    - "minimal": Column widths are adjusted to fit the content, and the header row(s) is frozen.
    - "default": Minimal + headers are bold, increased size, and colored.
    - "maximal": Default + alternating row colors in the properties sheet for each class in addition to extra
                 blank rows between classes and borders
    """

    Style = Literal["none", "minimal", "default", "maximal"]

    _main_header_by_sheet_name: ClassVar[dict[str, str]] = {
        "Properties": "Definition of Properties per Class",
        "Classes": "Definition of Classes",
        "Views": "Definition of Views",
        "Containers": "Definition of Containers",
    }
    style_options = get_args(Style)

    def __init__(self, styling: Style = "default", output_role: RoleTypes | None = None):
        if styling not in self.style_options:
            raise ValueError(f"Invalid styling: {styling}. Valid options are {self.style_options}")
        self.styling = styling
        self._styling_level = self.style_options.index(styling)
        self.output_role = output_role

    def export_to_file(self, rules: Rules, filepath: Path) -> None:
        """Exports transformation rules to excel file."""
        data = self.export(rules)
        try:
            data.save(filepath)
        finally:
            data.close()
        return None

    def export(self, rules: Rules) -> Workbook:
        rules = self._convert_to_output_role(rules, self.output_role)
        workbook = Workbook()
        # Remove default sheet named "Sheet"
        workbook.remove(workbook["Sheet"])

        dumped_rules = rules.model_dump(by_alias=True)
        if rules.is_reference:
            # Writes empty reference sheets
            empty: dict[str, Any] = {field_alias: None for field_alias in dumped_rules["Metadata"].keys()}
            empty["role"] = (self.output_role and self.output_role.value) or rules.metadata.role.value
            self._write_metadata_sheet(workbook, empty)
            self._write_sheets(workbook, {}, rules)
        else:
            self._write_metadata_sheet(workbook, dumped_rules["Metadata"])

        self._write_sheets(workbook, dumped_rules, rules, is_reference=rules.is_reference)

        if rules.is_reference:
            self._write_metadata_sheet(workbook, dumped_rules["Metadata"], is_reference=True)

        if self._styling_level > 0:
            self._adjust_column_widths(workbook)

        return workbook

    def _write_sheets(self, workbook: Workbook, dumped_rules: dict[str, Any], rules: Rules, is_reference: bool = False):
        for sheet_name, headers in rules.headers_by_sheet(by_alias=True).items():
            if sheet_name in ("Metadata", "prefixes", "Reference", "is_reference"):
                continue
            if is_reference:
                sheet = workbook.create_sheet(f"Ref{sheet_name}")
            else:
                sheet = workbook.create_sheet(sheet_name)

            # Reorder such that the first column is class + the first field of the subclass
            # of sheet entity. This is to make the properties/classes/views/containers sheet more readable.
            # For example, for the properties these that means class, property, name, description
            # instead of class, name, description, property
            move = len(SheetEntity.model_fields) - 1  # -1 is for the class field
            headers = headers[:1] + headers[move : move + 1] + headers[1:move] + headers[move + 1 :]

            main_header = self._main_header_by_sheet_name[sheet_name]
            sheet.append([main_header] + [""] * (len(headers) - 1))
            sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
            sheet.append(headers)

            fill_colors = itertools.cycle(["CADCFC", "FFFFFF"])
            fill_color = next(fill_colors)
            last_class: str | None = None
            item: dict[str, Any]
            for item in dumped_rules.get(sheet_name) or []:
                row = list(item.values())
                class_ = row[0]

                is_properties = sheet_name == "Properties"
                is_new_class = class_ != last_class and last_class is not None
                if self._styling_level > 2 and is_new_class and is_properties:
                    sheet.append([""] * len(headers))
                    for cell in sheet[sheet.max_row]:
                        cell.fill = PatternFill(fgColor=fill_color, patternType="solid")
                        side = Side(style="thin", color="000000")
                        cell.border = Border(left=side, right=side, top=side, bottom=side)
                    fill_color = next(fill_colors)

                # Need to do the same reordering as for the headers above
                row = row[:1] + row[move : move + 1] + row[1:move] + row[move + 1 :]
                sheet.append(row)
                if self._styling_level > 2 and is_properties:
                    for cell in sheet[sheet.max_row]:
                        cell.fill = PatternFill(fgColor=fill_color, patternType="solid")
                        side = Side(style="thin", color="000000")
                        cell.border = Border(left=side, right=side, top=side, bottom=side)
                last_class = class_

            if self._styling_level > 0:
                # This freezes all rows above the given row
                sheet.freeze_panes = sheet["A3"]

                sheet["A1"].alignment = Alignment(horizontal="center")

            if self._styling_level > 1:
                # Make the header row bold, larger, and colored
                sheet["A1"].font = Font(bold=True, size=20)
                sheet["A1"].fill = PatternFill(fgColor="FFC000", patternType="solid")
                for cell in sheet["2"]:
                    cell.font = Font(bold=True, size=14)

    def _write_metadata_sheet(self, workbook: Workbook, metadata: dict[str, Any], is_reference: bool = False) -> None:
        if is_reference:
            metadata_sheet = workbook.create_sheet("RefMetadata")
        else:
            metadata_sheet = workbook.create_sheet("Metadata")
        for key, value in metadata.items():
            metadata_sheet.append([key, value])

        if self._styling_level > 1:
            for cell in metadata_sheet["A"]:
                cell.font = Font(bold=True, size=12)

    @classmethod
    def _get_item_class(cls, annotation: GenericAlias) -> type[SheetEntity]:
        if not isinstance(annotation, GenericAlias):
            raise ValueError(f"Expected annotation to be a GenericAlias, but got {type(annotation)}")
        args = get_args(annotation)
        if len(args) != 1:
            raise ValueError(f"Expected annotation to have exactly one argument, but got {len(args)}")
        arg = args[0]
        if not issubclass(arg, SheetEntity):
            raise ValueError(f"Expected annotation to have a BaseModel argument, but got {type(arg)}")
        return arg

    @classmethod
    def _adjust_column_widths(cls, workbook: Workbook) -> None:
        for sheet in workbook:
            for column_cells in sheet.columns:
                try:
                    max_length = max(len(str(cell.value)) for cell in column_cells if cell.value is not None)
                except ValueError:
                    max_length = 0

                selected_column = column_cells[0]
                if isinstance(selected_column, MergedCell):
                    selected_column = column_cells[1]

                current = sheet.column_dimensions[selected_column.column_letter].width or (max_length + 0.5)
                sheet.column_dimensions[selected_column.column_letter].width = max(current, max_length + 0.5)
        return None
