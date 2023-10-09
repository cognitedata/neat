from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal, overload

import pandas as pd
from pydantic_core import ErrorDetails

from cognite.neat.rules.models import TransformationRules
from cognite.neat.rules.parser import RawTables, from_tables


class BaseImporter(ABC):
    def __init__(self, spreadsheet_path: Path | None = None):
        self.spreadsheet_path = spreadsheet_path

    @abstractmethod
    def to_tables(self) -> RawTables:
        raise NotImplementedError

    def to_spreadsheet(self, filepath: Path | None = None) -> None:
        filepath = filepath or self.spreadsheet_path
        if not filepath:
            raise ValueError("No filepath given")
        tables = self.to_tables()
        with pd.ExcelWriter(filepath) as writer:
            tables.Metadata.to_excel(writer, sheet_name="Metadata", header=False)
            tables.Classes.to_excel(writer, sheet_name="Classes", index=False, header=False)
            tables.Properties.to_excel(writer, sheet_name="Properties", index=False, header=False)

    @overload
    def to_rules(self, return_report: Literal[False] = False) -> TransformationRules:
        ...

    @overload
    def to_rules(
        self, return_report: Literal[True]
    ) -> tuple[TransformationRules | None, list[ErrorDetails] | None, list | None]:
        ...

    def to_rules(
        self, return_report: Literal[True, False] = False
    ) -> tuple[TransformationRules | None, list[ErrorDetails] | None, list | None] | TransformationRules:
        tables = self.to_tables()
        raw_dfs: dict[str, pd.DataFrame] = {
            "metadata": tables.Metadata,
            "classes": tables.Classes,
            "properties": tables.Properties,
        }
        return from_tables(raw_dfs=raw_dfs, return_report=return_report)
