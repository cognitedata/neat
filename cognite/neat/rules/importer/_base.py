import getpass
import warnings
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Literal, overload

import pandas as pd
from pydantic_core import ErrorDetails

from cognite.neat.rules import exceptions
from cognite.neat.rules.models import TransformationRules
from cognite.neat.rules.parser import RawTables, from_tables
from cognite.neat.utils.utils import generate_exception_report


class BaseImporter(ABC):
    def __init__(self, spreadsheet_path: Path | None = None, report_path: Path | None = None):
        self.spreadsheet_path = spreadsheet_path
        if self.spreadsheet_path and not report_path:
            self.report_path = self.spreadsheet_path.parent / "report.txt"
        else:
            self.report_path = Path.cwd() / "report.txt"

    @abstractmethod
    def to_tables(self) -> RawTables:
        raise NotImplementedError

    def to_spreadsheet(self, filepath: Path | None = None, validate_results: bool = True) -> None:
        filepath = filepath or self.spreadsheet_path
        if not filepath:
            raise ValueError("No filepath given")
        tables = self.to_tables()

        with pd.ExcelWriter(filepath) as writer:
            tables.Metadata.to_excel(writer, sheet_name="Metadata", header=False, index=False)

            # Add helper row to classes' sheet
            pd.DataFrame(
                data=[("Data Model Definition", "", "", "", "State", "", "", "Knowledge acquisition log", "", "", "")]
            ).to_excel(writer, sheet_name="Classes", index=False, header=False, startrow=0)
            tables.Classes.to_excel(writer, sheet_name="Classes", index=False, header=True, startrow=1)

            # Add helper row to properties' sheet
            pd.DataFrame(
                data=[
                    ["Data Model Definition"]
                    + [""] * 5
                    + ["Start"]
                    + [""] * 3
                    + ["Knowledge acquisition log"]
                    + [""] * 3
                ]
            ).to_excel(writer, sheet_name="Properties", index=False, header=False, startrow=0)
            tables.Properties.to_excel(writer, sheet_name="Properties", index=False, header=True, startrow=1)

            if not tables.Prefixes.empty:
                tables.Prefixes.to_excel(writer, sheet_name="Prefixes", index=False)

        if validate_results and self.report_path:
            self._validate_rules(tables)

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

        return from_tables(raw_dfs=tables, return_report=return_report)

    def _validate_rules(self, raw_tables: RawTables) -> None:
        _, validation_errors, validation_warnings = from_tables(raw_tables, return_report=True)

        report = ""
        if validation_errors:
            warnings.warn(
                exceptions.GeneratedTransformationRulesHasErrors(importer_type=self.__class__.__name__).message,
                category=exceptions.GeneratedTransformationRulesHasErrors,
                stacklevel=2,
            )
            report = generate_exception_report(validation_errors, "Errors")

        if validation_warnings:
            warnings.warn(
                exceptions.GeneratedTransformationRulesHasWarnings(importer_type=self.__class__.__name__).message,
                category=exceptions.GeneratedTransformationRulesHasWarnings,
                stacklevel=2,
            )
            report += generate_exception_report(validation_warnings, "Warnings")

        if report:
            self.report_path.write_text(report)

    def _default_metadata(self):
        return {
            "shortName": "NeatImport",
            "version": "0.1.0",
            "title": "Neat Imported Data Model",
            "created": datetime.now().replace(microsecond=0).isoformat(),
            "creator": getpass.getuser(),
            "description": f"Imported using {type(self).__name__}",
            "prefix": "neat",
        }
