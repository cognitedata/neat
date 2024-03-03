import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from pydantic_core import ErrorDetails

from ._base import Error, MultiValueError
from ._container_inconsistency import InconsistentContainerDefinition

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


@dataclass(frozen=True, order=True)
class SpreadsheetNotFound(Error):
    description: ClassVar[str] = "Spreadsheet not found"
    fix: ClassVar[str] = "Make sure to provide a valid spreadsheet"

    spreadsheet_name: str

    def message(self) -> str:
        return f"Spreadsheet {self.spreadsheet_name} not found"


@dataclass(frozen=True, order=True)
class MetadataSheetMissingOrFailed(Error):
    description: ClassVar[str] = "Metadata sheet is missing or it failed validation for one or more fields"
    fix: ClassVar[str] = "Make sure to define compliant Metadata sheet before proceeding"


@dataclass(frozen=True, order=True)
class SpreadsheetMissing(Error):
    description: ClassVar[str] = "Spreadsheet(s) is missing"
    fix: ClassVar[str] = "Make sure to provide compliant spreadsheet(s) before proceeding"

    missing_spreadsheets: list[str]

    def message(self) -> str:
        if len(self.missing_spreadsheets) == 1:
            return f"Spreadsheet {self.missing_spreadsheets[0]} is missing"
        else:
            return f"Spreadsheets {', '.join(self.missing_spreadsheets)} are missing"


@dataclass(frozen=True, order=True)
class ReadSpreadsheets(Error):
    description: ClassVar[str] = "Error reading spreadsheet(s)"
    fix: ClassVar[str] = "Is the excel document open in another program? Is the file corrupted?"

    error_message: str

    def message(self) -> str:
        return f"Error reading spreadsheet(s): {self.error_message}"


@dataclass(frozen=True, order=True)
class InvalidRole(Error):
    description: ClassVar[str] = "Invalid role"
    fix: ClassVar[str] = "Make sure to provide a valid role"

    provided_role: str

    def message(self) -> str:
        return f"Invalid role: {self.provided_role}"


@dataclass(frozen=True, order=True)
class InvalidSheetContent(Error, ABC):
    @classmethod
    @abstractmethod
    def from_pydantic_error(cls, error: ErrorDetails, header_row_by_sheet_name: dict[str, int] | None = None) -> Self:
        raise NotImplementedError

    @classmethod
    def from_pydantic_errors(
        cls, errors: list[ErrorDetails], header_row_by_sheet_name: dict[str, int] | None = None
    ) -> "list[Error]":
        output: list[Error] = []
        for error in errors:
            if raised_error := error.get("ctx", {}).get("error"):
                if isinstance(raised_error, MultiValueError):
                    for caught_error in raised_error.errors:
                        if isinstance(caught_error, InconsistentContainerDefinition):
                            property_header = (header_row_by_sheet_name or {}).get("Properties", 0) + 1
                            row_numbers = list(caught_error.row_numbers)
                            # The Error classes are immutable, so we have to reuse the set.
                            caught_error.row_numbers.clear()
                            for row_no in row_numbers:
                                # Adjusting the row number to the actual row number in the spreadsheet
                                caught_error.row_numbers.add(row_no + property_header)
                        output.append(caught_error)
                    continue

            if len(error["loc"]) == 4:
                sheet_name, *_ = error["loc"]
                error_cls = _INVALID_SPECIFICATION_BY_SHEET_NAME.get(
                    str(sheet_name), InvalidRowSpecificationUnknownSheet
                )
                output.append(error_cls.from_pydantic_error(error, header_row_by_sheet_name))
                continue

            raise NotImplementedError("Pydantic raised error not supported by this function.")
        return output


@dataclass(frozen=True, order=True)
class InvalidRowSpecification(InvalidSheetContent, ABC):
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
    def from_pydantic_error(cls, error: ErrorDetails, header_row_by_sheet_name: dict[str, int] | None = None) -> Self:
        sheet_name, *_, row, column = error["loc"]
        return cls(
            column=str(column),
            # +1 because excel is 1-indexed
            row=int(row) + (header_row_by_sheet_name or {}).get(str(sheet_name), 0) + 1,
            type=error["type"],
            msg=error["msg"],
            input=error.get("input"),
            url=str(url) if (url := error.get("url")) else None,
        )


@dataclass(frozen=True, order=True)
class InvalidPropertySpecification(InvalidRowSpecification):
    sheet_name = "Properties"


@dataclass(frozen=True, order=True)
class InvalidClassSpecification(InvalidRowSpecification):
    sheet_name = "Classes"


@dataclass(frozen=True, order=True)
class InvalidContainerSpecification(InvalidRowSpecification):
    sheet_name = "Containers"


@dataclass(frozen=True, order=True)
class InvalidViewSpecification(InvalidRowSpecification):
    sheet_name = "Views"


@dataclass(frozen=True, order=True)
class InvalidRowSpecificationUnknownSheet(InvalidRowSpecification):
    sheet_name = "Unknown"

    actual_sheet_name: str

    @classmethod
    def from_pydantic_error(cls, error: ErrorDetails, header_row_by_sheet_name: dict[str, int] | None = None) -> Self:
        sheet_name, *_, row, column = error["loc"]
        return cls(
            column=str(column),
            # +1 because excel is 1-indexed
            row=int(row) + (header_row_by_sheet_name or {}).get(str(sheet_name), 0) + 1,
            actual_sheet_name=str(sheet_name),
            type=error["type"],
            msg=error["msg"],
            input=error.get("input"),
            url=str(url) if (url := error.get("url")) else None,
        )


_INVALID_SPECIFICATION_BY_SHEET_NAME = {
    cls_.sheet_name: cls_ for cls_ in InvalidRowSpecification.__subclasses__() if cls_ is not InvalidRowSpecification
}
