from abc import ABC
from dataclasses import dataclass
from typing import Any, ClassVar, Self

from pydantic_core import ErrorDetails

from ._base import Error


@dataclass
class SpreadsheetNotFound(Error):
    description: ClassVar[str] = "Spreadsheet not found"
    fix: ClassVar[str] = "Make sure to provide a valid spreadsheet"

    spreadsheet_name: str

    def message(self) -> str:
        return f"Spreadsheet {self.spreadsheet_name} not found"


@dataclass
class MetadataSheetMissingOrFailed(Error):
    description: ClassVar[str] = "Metadata sheet is missing or it failed validation for one or more fields"
    fix: ClassVar[str] = "Make sure to define compliant Metadata sheet before proceeding"


@dataclass
class SpreadsheetMissing(Error):
    description: ClassVar[str] = "Spreadsheet(s) is missing"
    fix: ClassVar[str] = "Make sure to provide compliant spreadsheet(s) before proceeding"

    missing_spreadsheets: list[str]

    def message(self) -> str:
        if len(self.missing_spreadsheets) == 1:
            return f"Spreadsheet {self.missing_spreadsheets[0]} is missing"
        else:
            return f"Spreadsheets {', '.join(self.missing_spreadsheets)} are missing"


@dataclass
class ReadSpreadsheets(Error):
    description: ClassVar[str] = "Error reading spreadsheet(s)"
    fix: ClassVar[str] = "Is the excel document open in another program? Is the file corrupted?"

    error_message: str

    def message(self) -> str:
        return f"Error reading spreadsheet(s): {self.error_message}"


@dataclass
class InvalidRole(Error):
    description: ClassVar[str] = "Invalid role"
    fix: ClassVar[str] = "Make sure to provide a valid role"

    provided_role: str

    def message(self) -> str:
        return f"Invalid role: {self.provided_role}"


@dataclass
class InvalidSheetSpecification(Error, ABC):
    description: ClassVar[str] = "This is a generic class for all invalid specifications."
    fix: ClassVar[str] = "Follow the instruction in the error message."
    sheet_name: ClassVar[str]

    column: str
    row: int
    type: str
    msg: str
    input: Any
    url: str | None

    @classmethod
    def from_pydantic_error(cls, error: ErrorDetails) -> Self:
        *_, row, column = error["loc"]
        return cls(
            column=str(column),
            row=int(row),
            type=error["type"],
            msg=error["msg"],
            input=error.get("input"),
            url=str(url) if (url := error.get("url")) else None,
        )


@dataclass
class InvalidPropertySpecification(InvalidSheetSpecification):
    sheet_name = "Properties"


@dataclass
class InvalidClassSpecification(InvalidSheetSpecification):
    sheet_name = "Classes"


@dataclass
class InvalidContainerSpecification(InvalidSheetSpecification):
    sheet_name = "Containers"


@dataclass
class InvalidViewSpecification(InvalidSheetSpecification):
    sheet_name = "Views"


INVALID_SPECIFICATION_BY_SHEET_NAME = {
    cls_.sheet_name: cls_
    for cls_ in InvalidSheetSpecification.__subclasses__()
    if cls_ is not InvalidSheetSpecification
}
