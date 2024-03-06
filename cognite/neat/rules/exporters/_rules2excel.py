from pathlib import Path
from types import GenericAlias
from typing import Any, ClassVar, Literal, cast, get_args

from openpyxl import Workbook

from cognite.neat.rules._shared import Rules
from cognite.neat.rules.models._rules.base import SheetEntity, SheetList

from ._base import BaseExporter


class ExcelExporter(BaseExporter[Workbook]):
    """Export rules to Excel.

    Args:
        styling: The styling to use for the Excel file. Defaults to "default". See below for details
            on the different styles.

    The following styles are available:

    - "none":    No styling is applied.
    - "minimal": Column widths are adjusted to fit the content, and the header row(s) is frozen.
    - "default": Minimal + headers are bold, increased size, and colored.
    - "maximal": Default + alternating row colors in the properties sheet for each class in addition to extra
                 blank rows between classes.
    """

    Style = Literal["none", "minimal", "default", "maximal"]

    _main_header_by_sheet_name: ClassVar[dict[str, str]] = {
        "Properties": "Definition of properties per class",
        "Classes": "Definition of classes",
        "Views": "Definition of views",
        "Containers": "Definition of containers",
    }
    style_options = get_args(Style)

    def __init__(self, styling: Style = "default"):
        self.styling = styling

    def export_to_file(self, filepath: Path, rules: Rules) -> None:
        """Exports transformation rules to excel file."""
        data = self.export(rules)
        try:
            data.save(filepath)
        finally:
            data.close()
        return None

    def export(self, rules: Rules) -> Workbook:
        workbook = Workbook()
        # Remove default sheet named "Sheet"
        workbook.remove(workbook["Sheet"])

        metadata_sheet = workbook.create_sheet("Metadata")
        metadata_sheet.append(["role", rules.metadata.role.value])
        for key, value in rules.metadata.model_dump().items():
            metadata_sheet.append([key, value])

        field_names_by_sheet_name = {
            field.alias or field_name: field_name for field_name, field in rules.model_fields.items()
        }
        for sheet_name in ["Properties", "Classes", "Views", "Containers"]:
            if sheet_name not in field_names_by_sheet_name:
                continue
            field_name = field_names_by_sheet_name[sheet_name]
            sheet = workbook.create_sheet(sheet_name)
            data = getattr(rules, field_name)
            if data is None:
                continue
            if not isinstance(data, SheetList):
                raise ValueError(f"Expected {field_name} to be a SheetList, but got {type(data)}")
            annotation = data.model_fields["data"].annotation
            item_cls = self._get_item_class(cast(GenericAlias, annotation))
            skip = {"validators_to_skip"}
            headers = [
                field.alias or field_name
                for field_name, field in item_cls.model_fields.items()
                if field_name not in skip
            ]
            # Reorder such that the SheetEntity fields are after the first two columns
            # For the properties sheet the first two columns as class and property.
            move = len(SheetEntity.model_fields) - 1
            headers = headers[move : move + 2] + headers[:move] + headers[move + 2 :]
            main_header = self._main_header_by_sheet_name[sheet_name]
            sheet.append([main_header] + [""] * (len(headers) - 1))
            sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
            sheet.append(headers)
            item: dict[str, Any]
            for item in data.model_dump()["data"]:
                row = list(item.values())
                # Need to do the same reordering as for the headers
                row = row[move : move + 2] + row[:move] + row[move + 2 :]
                sheet.append(row)

        return workbook

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
