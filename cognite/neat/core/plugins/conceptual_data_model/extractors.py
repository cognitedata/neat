from pathlib import Path
from typing import Any

from cognite.neat.core._rules._shared import ReadRules
from cognite.neat.core._rules.importers._spreadsheet2rules import ExcelImporter


class ConceptualDataModelExtractor:
    __slots__ = ()

    def __init__(self):
        pass

    def extract(self, source: Any, *args, **kwargs) -> None:
        pass


class Excel(ConceptualDataModelExtractor):
    def extract(self, source: str, *, validate: bool = False) -> ReadRules:
        """
        Extracts the rules from the Excel file.

        Args:
            filepath (str): Path to the Excel file.

        Returns:
            ReadRules: The extracted rules.
        """
        read_rules = ExcelImporter(filepath=Path(source)).to_rules()
        if not validate:
            return read_rules
        else:
            return read_rules.rules.as_verified_rules()
