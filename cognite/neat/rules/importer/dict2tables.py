from pathlib import Path
from typing import Any

from cognite.neat.rules.parser import RawTables

from ._base import BaseImporter


class DictImporter(BaseImporter):
    """
    Importer for an arbitrary dictionary.

    Args:
        data: file with JSON.
        spreadsheet_path: Path to write the transformation rules to in the .to_spreadsheet() method.
        report_path: Path to write the report to in the .to_spreadsheet() method.
    """

    def __init__(self, data: dict[str, Any], spreadsheet_path: Path | None = None, report_path: Path | None = None):
        self.data = data
        super().__init__(spreadsheet_path=spreadsheet_path, report_path=report_path)

    def to_tables(self) -> RawTables:
        raise NotImplementedError
