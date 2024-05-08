from __future__ import annotations

import itertools
from datetime import datetime
from pathlib import Path
from types import GenericAlias
from typing import Any, ClassVar, Literal, cast, get_args

from openpyxl import Workbook
from openpyxl.cell import MergedCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

from cognite.neat.rules._shared import Rules
from cognite.neat.rules.models import (
    DMSRules,
    DomainRules,
    InformationRules,
    RoleTypes,
    SchemaCompleteness,
    SheetEntity,
)

from ._base import BaseExporter


class ExcelExporter(BaseExporter[Workbook]):
    """Export rules to Excel.

    Args:
        styling: The styling to use for the Excel file. Defaults to "default". See below for details
            on the different styles.
        output_role: The role to use for the exported spreadsheet. If provided, the rules will be converted to
            this role formate before being written to excel. If not provided, the role from the rules will be used.
        new_model_id: The new model ID to use for the exported spreadsheet. This is only applicable if the input
            rules have 'is_reference' set. If provided, the model ID will be used to automatically create the
            new metadata sheet in the Excel file.
        dump_as: This determines how the rules are written to the Excel file. An Excel file has up to three sets of
           sheets: user, last, and reference. The user sheets are used for inputting rules from a user. The last sheets
           are used for the last version of the same model as the user, while the reference sheets are used for
           the model the user is building on. The options are:
             * "user": The rules are written to the user sheets. This is used when you want to modify the rules
                directly and potentially change the model. This is useful when you have imported the data model
                from outside CDF and you want to modify it before you write it to CDF.
             * "last": The rules are written to the last sheets. This is used when you want to extend the rules,
               but have validation that you are not breaking the existing model. This is used when you want to
               change a model that has already been published to CDF and that model is in production.
             * "reference": The rules are written to the reference sheets. This is typically used when you want to build
               a new solution on top of an enterprise model.

    The following styles are available:

    - "none":    No styling is applied.
    - "minimal": Column widths are adjusted to fit the content, and the header row(s) is frozen.
    - "default": Minimal + headers are bold, increased size, and colored.
    - "maximal": Default + alternating row colors in the properties sheet for each class in addition to extra
                 blank rows between classes and borders
    """

    Style = Literal["none", "minimal", "default", "maximal"]
    DumpOptions = Literal["user", "last", "reference"]
    _main_header_by_sheet_name: ClassVar[dict[str, str]] = {
        "Properties": "Definition of Properties per Class",
        "Classes": "Definition of Classes",
        "Views": "Definition of Views",
        "Containers": "Definition of Containers",
    }
    style_options = get_args(Style)
    dump_options = get_args(DumpOptions)

    def __init__(
        self,
        styling: Style = "default",
        output_role: RoleTypes | None = None,
        new_model_id: tuple[str, str, str] | None = None,
        dump_as: DumpOptions = "user",
    ):
        if styling not in self.style_options:
            raise ValueError(f"Invalid styling: {styling}. Valid options are {self.style_options}")
        if dump_as not in self.dump_options:
            raise ValueError(f"Invalid dump_as: {dump_as}. Valid options are {self.dump_options}")
        self.styling = styling
        self._styling_level = self.style_options.index(styling)
        self.output_role = output_role
        self.new_model_id = new_model_id
        self.dump_as = dump_as

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

        dumped_rules: dict[str, Any]
        dumped_reference_rules: dict[str, Any] | None = None
        if self.dump_as == "reference":
            # Writes empty reference sheets
            dumped_rules = {
                "Metadata": self._create_metadata_sheet_user_rules(rules),
            }
            dumped_rules["Metadata"]["role"] = (
                self.output_role and self.output_role.value
            ) or rules.metadata.role.value
            dumped_reference_rules = rules.reference_self().model_dump(by_alias=True)
        else:
            dumped_rules = rules.model_dump(by_alias=True)
            if rules.reference:
                dumped_reference_rules = rules.reference.model_dump(by_alias=True)

        self._write_metadata_sheet(workbook, dumped_rules["Metadata"])
        self._write_sheets(workbook, dumped_rules, rules)
        if dumped_reference_rules:
            self._write_sheets(workbook, dumped_reference_rules, rules, is_reference=True)
            self._write_metadata_sheet(workbook, dumped_reference_rules["Metadata"], is_reference=True)

        if self._styling_level > 0:
            self._adjust_column_widths(workbook)

        return workbook

    def _write_sheets(self, workbook: Workbook, dumped_rules: dict[str, Any], rules: Rules, is_reference: bool = False):
        for sheet_name, headers in rules.headers_by_sheet(by_alias=True).items():
            if sheet_name in ("Metadata", "prefixes", "Reference", "Last"):
                continue
            if is_reference:
                sheet = workbook.create_sheet(f"Ref{sheet_name}")
            else:
                sheet = workbook.create_sheet(sheet_name)

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
        # Excel does not support timezone in datetime strings
        if isinstance(metadata.get("created"), datetime):
            metadata["created"] = metadata["created"].replace(tzinfo=None)
        if isinstance(metadata.get("updated"), datetime):
            metadata["updated"] = metadata["updated"].replace(tzinfo=None)

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
        for sheet_ in workbook:
            sheet = cast(Worksheet, sheet_)
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

    def _create_metadata_sheet_user_rules(self, rules: Rules) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            field_alias: None for field_alias in rules.metadata.model_dump(by_alias=True).keys()
        }
        if "creator" in metadata:
            metadata["creator"] = "YOUR NAME"

        if isinstance(rules, DomainRules):
            return metadata
        elif isinstance(rules, DMSRules):
            existing_model_id = (rules.metadata.space, rules.metadata.external_id, rules.metadata.version)
        elif isinstance(rules, InformationRules):
            existing_model_id = (rules.metadata.prefix, rules.metadata.name, rules.metadata.version)
        else:
            raise ValueError(f"Unsupported rules type: {type(rules)}")
        existing_metadata = rules.metadata.model_dump(by_alias=True)
        if isinstance(existing_metadata["created"], datetime):
            metadata["created"] = existing_metadata["created"].replace(tzinfo=None)
        if isinstance(existing_metadata["updated"], datetime):
            metadata["updated"] = existing_metadata["updated"].replace(tzinfo=None)
        # Excel does not support timezone in datetime strings
        now_iso = datetime.now().replace(tzinfo=None).isoformat()
        is_info = isinstance(rules, InformationRules)
        is_dms = not is_info
        is_extension = self.new_model_id is not None
        is_solution = is_extension and self.new_model_id != existing_model_id

        if is_solution:
            metadata["prefix" if is_info else "space"] = self.new_model_id[0]  # type: ignore[index]
            metadata["title" if is_info else "externalId"] = self.new_model_id[1]  # type: ignore[index]
            metadata["version"] = self.new_model_id[2]  # type: ignore[index]
        else:
            metadata["prefix" if is_info else "space"] = existing_model_id[0]
            metadata["title" if is_info else "externalId"] = existing_model_id[1]
            metadata["version"] = existing_model_id[2]

        if is_solution and is_info:
            metadata["namespace"] = f"http://purl.org/{self.new_model_id[0]}/"  # type: ignore[index]
        elif is_info:
            metadata["namespace"] = existing_metadata["namespace"]

        if is_solution and is_dms:
            metadata["name"] = self.new_model_id[1]  # type: ignore[index]

        if is_solution:
            metadata["created"] = now_iso
        else:
            metadata["created"] = existing_metadata["created"]

        if is_solution or is_extension:
            metadata["updated"] = now_iso
        else:
            metadata["updated"] = existing_metadata["updated"]

        if is_solution:
            metadata["creator"] = "YOUR NAME"
        else:
            metadata["creator"] = existing_metadata["creator"]

        if not is_solution:
            metadata["description"] = existing_metadata["description"]

        if is_extension:
            metadata["schema"] = SchemaCompleteness.extended.value
        else:
            metadata["schema"] = SchemaCompleteness.complete.value

        metadata["extension"] = "addition"

        return metadata
