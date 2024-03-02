from abc import ABC
from dataclasses import dataclass
from typing import ClassVar

from ._base import ValidationError


@dataclass
class SheetContent(ValidationError, ABC):
    ...


@dataclass
class SpreadsheetNotFound(ValidationError):
    description: ClassVar[str] = "Spreadsheet not found"
    fix: ClassVar[str] = "Make sure to provide a valid spreadsheet"

    spreadsheet_name: str

    def message(self) -> str:
        return f"Spreadsheet {self.spreadsheet_name} not found"


@dataclass
class MetadataSheetMissingOrFailed(ValidationError):
    description: ClassVar[str] = "Metadata sheet is missing or it failed validation for one or more fields"
    fix: ClassVar[str] = "Make sure to define compliant Metadata sheet before proceeding"


@dataclass
class SpreadsheetMissing(ValidationError):
    description: ClassVar[str] = "Spreadsheet(s) is missing"
    fix: ClassVar[str] = "Make sure to provide compliant spreadsheet(s) before proceeding"

    missing_spreadsheets: list[str]

    def message(self) -> str:
        if len(self.missing_spreadsheets) == 1:
            return f"Spreadsheet {self.missing_spreadsheets[0]} is missing"
        else:
            return f"Spreadsheets {', '.join(self.missing_spreadsheets)} are missing"


@dataclass
class ReadSpreadsheets(ValidationError):
    description: ClassVar[str] = "Error reading spreadsheet(s)"
    fix: ClassVar[str] = "Is the excel document open in another program? Is the file corrupted?"

    error_message: str

    def message(self) -> str:
        return f"Error reading spreadsheet(s): {self.error_message}"


@dataclass
class InvalidRole(ValidationError):
    description: ClassVar[str] = "Invalid role"
    fix: ClassVar[str] = "Make sure to provide a valid role"

    provided_role: str

    def message(self) -> str:
        return f"Invalid role: {self.provided_role}"
