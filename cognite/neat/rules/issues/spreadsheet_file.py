from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from .base import NeatValidationError

__all__ = [
    "SpreadsheetFileError",
    "SpreadsheetNotFoundError",
    "MetadataSheetMissingOrFailedError",
    "SheetMissingError",
    "ReadSpreadsheetsError",
    "InvalidRoleError",
]


@dataclass(frozen=True)
class SpreadsheetFileError(NeatValidationError, ABC):
    description = "Error when reading spreadsheet"
    filepath: Path


@dataclass(frozen=True)
class SpreadsheetNotFoundError(SpreadsheetFileError):
    description: ClassVar[str] = "Spreadsheet not found"
    fix: ClassVar[str] = "Make sure to provide a valid spreadsheet"

    def message(self) -> str:
        return f"Spreadsheet {self.filepath.name} not found"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["spreadsheet_name"] = str(self.filepath)
        return output


@dataclass(frozen=True)
class MetadataSheetMissingOrFailedError(SpreadsheetFileError):
    description: ClassVar[str] = "Metadata sheet is missing or it failed validation for one or more fields"
    fix: ClassVar[str] = "Make sure to define compliant Metadata sheet before proceeding"
    hint: str | None = None
    sheet_name: str = "Metadata"

    def message(self) -> str:
        output = (
            f" {self.sheet_name} sheet is missing or it failed"
            + f" validation for one or more fields in {self.filepath.name}. "
            + self.fix
        )
        if self.hint:
            output += f" Hint: {self.hint}"
        return output


@dataclass(frozen=True)
class RoleMissingOrUnsupportedError(SpreadsheetFileError):
    description: ClassVar[str] = "Role field in Metadata sheet is missing or its value is unsupported"
    fix: ClassVar[str] = "Make sure to define compliant role in Metadata sheet before proceeding"

    hint: str | None = None

    def message(self) -> str:
        output = (
            f"Role field in Metadata sheet is missing or its value is unsupported {self.filepath.name}. " + self.fix
        )
        if self.hint:
            output += f" Hint: {self.hint}"
        return output


@dataclass(frozen=True)
class RoleMismatchError(SpreadsheetFileError):
    description: ClassVar[str] = "Roles between user and reference Metadata sheets do not match"
    fix: ClassVar[str] = "Make sure that both user and reference Metadata sheets have the same role defined"

    hint: str | None = None

    def message(self) -> str:
        output = f"Roles between user and reference Metadata sheets do not match {self.filepath.name}. " + self.fix
        if self.hint:
            output += f" Hint: {self.hint}"
        return output


@dataclass(frozen=True)
class SchemaMissingOrUnsupportedError(SpreadsheetFileError):
    description: ClassVar[str] = "Schema field in Metadata sheet is missing or its value unsupported"
    fix: ClassVar[str] = "Make sure to define compliant schema in Metadata sheet before proceeding"

    hint: str | None = None

    def message(self) -> str:
        output = (
            f"Schema field in Metadata sheet is missing or its value unsupported in file {self.filepath.name}. "
            + self.fix
        )
        if self.hint:
            output += f" Hint: {self.hint}"
        return output


@dataclass(frozen=True)
class SheetMissingError(SpreadsheetFileError):
    description: ClassVar[str] = "Spreadsheet(s) is missing"
    fix: ClassVar[str] = "Make sure to provide compliant spreadsheet(s) before proceeding"

    missing_spreadsheets: list[str]

    def message(self) -> str:
        if len(self.missing_spreadsheets) == 1:
            return f"Spreadsheet {self.missing_spreadsheets[0]} is missing"
        else:
            return f"Spreadsheets {', '.join(self.missing_spreadsheets)} are missing"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["missing_spreadsheets"] = self.missing_spreadsheets
        return output


@dataclass(frozen=True)
class ReadSpreadsheetsError(SpreadsheetFileError):
    description: ClassVar[str] = "Error reading spreadsheet(s)"
    fix: ClassVar[str] = "Is the excel document open in another program? Is the file corrupted?"

    error_message: str

    def message(self) -> str:
        return f"Error reading spreadsheet {self.filepath.name}: {self.error_message}"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["error_message"] = self.error_message
        return output


@dataclass(frozen=True)
class InvalidRoleError(NeatValidationError):
    description: ClassVar[str] = "Invalid role"
    fix: ClassVar[str] = "Make sure to provide a valid role"

    provided_role: str

    def message(self) -> str:
        return f"Invalid role: {self.provided_role}"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["provided_role"] = self.provided_role
        return output
