from pathlib import Path

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from cognite.neat.rules._shared import Rules
from cognite.neat.rules.models._rules.base import BaseMetadata

from ._base import BaseExporter


class ExcelExporter(BaseExporter[Workbook]):
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
        self._append_metadata(metadata_sheet, rules.metadata)
        return workbook

    def _append_metadata(self, sheet: Worksheet, metadata: BaseMetadata) -> None:
        raise NotImplementedError
