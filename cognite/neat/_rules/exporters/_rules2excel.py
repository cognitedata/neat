from __future__ import annotations

import itertools
import json
from datetime import datetime, timezone
from pathlib import Path
from types import GenericAlias
from typing import Any, ClassVar, Literal, cast, get_args

from openpyxl import Workbook
from openpyxl.cell import MergedCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet
from rdflib import Namespace

from cognite.neat._rules._shared import VerifiedRules
from cognite.neat._rules.models import (
    ExtensionCategory,
    SchemaCompleteness,
    SheetRow,
)
from cognite.neat._rules.models.dms import DMSMetadata
from cognite.neat._rules.models.information import InformationMetadata
from cognite.neat._rules.models.information._rules import InformationRules

from ._base import BaseExporter

MAX_COLUMN_WIDTH = 70.0


class ExcelExporter(BaseExporter[VerifiedRules, Workbook]):
    """Export rules to Excel.

    Args:
        styling: The styling to use for the Excel file. Defaults to "default". See below for details
            on the different styles.
        new_model_id: The new model ID to use for the exported spreadsheet. This is only applicable if the input
            rules have 'is_reference' set. If provided, the model ID will be used to automatically create the
            new metadata sheet in the Excel file. The model id is expected to be a tuple of (prefix, title)
            (space, external_id) for InformationRules and DMSRules respectively.

        sheet_prefix: The prefix to use for the sheet names in the Excel file. Defaults to an empty string.

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
        "Nodes": "Definition of Nodes",
        "Enum": "Definition of Enum Collections",
    }
    style_options = get_args(Style)
    dump_options = get_args(DumpOptions)

    def __init__(
        self,
        styling: Style = "default",
        new_model_id: tuple[str, str] | None = None,
        sheet_prefix: str | None = None,
        reference_rules_with_prefix: tuple[VerifiedRules, str] | None = None,
    ):
        self.sheet_prefix = sheet_prefix or ""
        if styling not in self.style_options:
            raise ValueError(f"Invalid styling: {styling}. Valid options are {self.style_options}")
        self.styling = styling
        self._styling_level = self.style_options.index(styling)
        self.new_model_id = new_model_id
        self.reference_rules_with_prefix = reference_rules_with_prefix

    @property
    def description(self) -> str:
        return "Export verified model to Excel."

    def export_to_file(self, rules: VerifiedRules, filepath: Path) -> None:
        """Exports transformation rules to excel file."""
        data = self.export(rules)
        try:
            data.save(filepath)
        finally:
            data.close()
        return None

    def export(self, rules: VerifiedRules) -> Workbook:
        workbook = Workbook()
        # Remove default sheet named "Sheet"
        workbook.remove(workbook["Sheet"])

        dumped_user_rules: dict[str, Any] = rules.dump(by_alias=True)

        self._write_metadata_sheet(workbook, dumped_user_rules["Metadata"], sheet_prefix=self.sheet_prefix)
        self._write_sheets(workbook, dumped_user_rules, rules, sheet_prefix=self.sheet_prefix)
        if self.reference_rules_with_prefix:
            reference_rules, prefix = self.reference_rules_with_prefix
            dumped_reference_rules = reference_rules.dump(entities_exclude_defaults=False, by_alias=True)
            self._write_sheets(workbook, dumped_reference_rules, reference_rules, sheet_prefix=prefix)
            self._write_metadata_sheet(workbook, dumped_reference_rules["Metadata"], sheet_prefix=prefix)

        if isinstance(rules, InformationRules) and rules.prefixes:
            self._write_prefixes_sheet(workbook, rules.prefixes)

        if self._styling_level > 0:
            self._adjust_column_widths(workbook)

        return workbook

    def _write_sheets(
        self,
        workbook: Workbook,
        dumped_rules: dict[str, Any],
        rules: VerifiedRules,
        sheet_prefix: str = "",
    ):
        for sheet_name, headers in rules.headers_by_sheet(by_alias=True).items():
            if sheet_name in ("Metadata", "Prefixes", "Reference", "Last"):
                continue
            sheet = workbook.create_sheet(f"{sheet_prefix}{sheet_name}")

            main_header = self._main_header_by_sheet_name[sheet_name]
            sheet.append([main_header] + [""] * (len(headers) - 1))

            if headers[0] == "Neat ID":
                # Move the Neat ID to the end of the columns
                headers = headers[1:] + ["Neat ID"]

            sheet.append(headers)

            fill_colors = itertools.cycle(["CADCFC", "FFFFFF"])
            fill_color = next(fill_colors)
            last_class: str | None = None
            item: dict[str, Any]
            for item in dumped_rules.get(sheet_name) or []:
                if "Neat ID" in item:
                    # Move the Neat ID to the end of the columns
                    item["Neat ID"] = item.pop("Neat ID")
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

                sheet["A1"].alignment = Alignment(horizontal="left")

            if self._styling_level > 1:
                # Make the header row bold, larger, and colored
                for cell, *_ in sheet.iter_cols(min_row=1, max_row=1, min_col=1, max_col=len(headers)):
                    cell.font = Font(bold=True, size=20)
                    cell.fill = PatternFill(fgColor="FFC000", patternType="solid")
                for cell in sheet["2"]:
                    cell.font = Font(bold=True, size=14)

    def _write_metadata_sheet(self, workbook: Workbook, metadata: dict[str, Any], sheet_prefix: str = "") -> None:
        # Excel does not support timezone in datetime strings
        if isinstance(metadata.get("created"), datetime):
            metadata["created"] = metadata["created"].replace(tzinfo=None)
        if isinstance(metadata.get("updated"), datetime):
            metadata["updated"] = metadata["updated"].replace(tzinfo=None)

        metadata_sheet = workbook.create_sheet(f"{sheet_prefix}Metadata")
        for key, value in metadata.items():
            metadata_sheet.append([key, value])

        if self._styling_level > 1:
            for cell in metadata_sheet["A"]:
                cell.font = Font(bold=True, size=12)

    def _write_prefixes_sheet(self, workbook: Workbook, prefixes: dict[str, Namespace]) -> None:
        metadata_sheet = workbook.create_sheet("Prefixes")
        metadata_sheet.append(["Prefix", "Namespace"])
        for key, value in prefixes.items():
            metadata_sheet.append([key, value])

        if self._styling_level > 1:
            for cell in metadata_sheet["A"]:
                cell.font = Font(bold=True, size=12)

    @classmethod
    def _get_item_class(cls, annotation: GenericAlias) -> type[SheetRow]:
        if not isinstance(annotation, GenericAlias):
            raise ValueError(f"Expected annotation to be a GenericAlias, but got {type(annotation)}")
        args = get_args(annotation)
        if len(args) != 1:
            raise ValueError(f"Expected annotation to have exactly one argument, but got {len(args)}")
        arg = args[0]
        if not issubclass(arg, SheetRow):
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

                current = sheet.column_dimensions[selected_column.column_letter].width or (max_length + 0.5)  # type: ignore[union-attr]
                sheet.column_dimensions[selected_column.column_letter].width = min(  # type: ignore[union-attr]
                    max(current, max_length + 0.5), MAX_COLUMN_WIDTH
                )
        return None


class _MetadataCreator:
    creator_name = "<YOUR NAME>"

    def __init__(
        self,
        action: Literal["create", "update"],
        new_model_id: tuple[str, str] | None = None,
    ):
        self.action = action
        self.new_model_id = new_model_id or ("YOUR_SPACE", "YOUR_EXTERNAL_ID")

    def create(self, metadata: InformationMetadata | DMSMetadata) -> dict[str, Any]:
        now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
        if self.action == "update":
            output = json.loads(metadata.model_dump_json(by_alias=True))
            # This is the same for Information and DMS
            output["updated"] = now.isoformat()
            output["schema"] = SchemaCompleteness.extended.value
            output["extension"] = ExtensionCategory.addition.value
            if value := output.get("creator"):
                output["creator"] = f"{value}, {self.creator_name}"
            else:
                output["creator"] = self.creator_name
            return output

        new_metadata = self._create_new_info(now)
        if isinstance(metadata, DMSMetadata):
            from cognite.neat._rules.transformers._converters import _InformationRulesConverter

            output_metadata: DMSMetadata | InformationMetadata = _InformationRulesConverter._convert_metadata_to_dms(
                new_metadata
            )
        elif isinstance(metadata, InformationMetadata):
            output_metadata = new_metadata
        else:
            raise ValueError(f"Bug in Neat: Unknown metadata type: {type(metadata)}")

        created = json.loads(output_metadata.model_dump_json(by_alias=True))
        created.pop("extension", None)
        return created

    def _create_new_info(self, now: datetime) -> InformationMetadata:
        return InformationMetadata(
            space=self.new_model_id[0],
            external_id=self.new_model_id[1],
            description=None,
            version="1",
            created=now,
            updated=now,
            creator=[self.creator_name],
            name=self.new_model_id[1],
        )
