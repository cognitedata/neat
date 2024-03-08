import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import total_ordering
from typing import Any, ClassVar

from pydantic_core import ErrorDetails

from cognite.neat.utils.spreadsheet import SpreadsheetRead

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

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["spreadsheet_name"] = self.spreadsheet_name
        return output


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

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["missing_spreadsheets"] = self.missing_spreadsheets
        return output


@dataclass(frozen=True, order=True)
class ReadSpreadsheets(Error):
    description: ClassVar[str] = "Error reading spreadsheet(s)"
    fix: ClassVar[str] = "Is the excel document open in another program? Is the file corrupted?"

    error_message: str

    def message(self) -> str:
        return f"Error reading spreadsheet(s): {self.error_message}"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["error_message"] = self.error_message
        return output


@dataclass(frozen=True, order=True)
class InvalidRole(Error):
    description: ClassVar[str] = "Invalid role"
    fix: ClassVar[str] = "Make sure to provide a valid role"

    provided_role: str

    def message(self) -> str:
        return f"Invalid role: {self.provided_role}"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["provided_role"] = self.provided_role
        return output


@dataclass(frozen=True, order=True)
class InvalidSheetContent(Error, ABC):
    @classmethod
    @abstractmethod
    def from_pydantic_error(
        cls, error: ErrorDetails, read_info_by_sheet: dict[str, SpreadsheetRead] | None = None
    ) -> Self:
        raise NotImplementedError

    @classmethod
    def from_pydantic_errors(
        cls, errors: list[ErrorDetails], read_info_by_sheet: dict[str, SpreadsheetRead] | None = None, **kwargs: Any
    ) -> "list[Error]":
        output: list[Error] = []
        for error in errors:
            if raised_error := error.get("ctx", {}).get("error"):
                if isinstance(raised_error, MultiValueError):
                    for caught_error in raised_error.errors:
                        reader = (read_info_by_sheet or {}).get("Properties", SpreadsheetRead())
                        if isinstance(caught_error, InconsistentContainerDefinition):
                            row_numbers = list(caught_error.row_numbers)
                            # The Error classes are immutable, so we have to reuse the set.
                            caught_error.row_numbers.clear()
                            for row_no in row_numbers:
                                # Adjusting the row number to the actual row number in the spreadsheet
                                caught_error.row_numbers.add(reader.adjusted_row_number(row_no))
                        if isinstance(caught_error, InvalidRowSpecification):
                            # Adjusting the row number to the actual row number in the spreadsheet
                            new_row = reader.adjusted_row_number(caught_error.row)
                            # The error is frozen, so we have to use __setattr__ to change the row number
                            object.__setattr__(caught_error, "row", new_row)
                        output.append(caught_error)
                    continue

            if len(error["loc"]) >= 4:
                sheet_name, *_ = error["loc"]
                error_cls = _INVALID_SPECIFICATION_BY_SHEET_NAME.get(
                    str(sheet_name), InvalidRowSpecificationUnknownSheet
                )
                output.append(error_cls.from_pydantic_error(error, read_info_by_sheet))
                continue

            raise NotImplementedError("Pydantic raised error not supported by this function.")
        return output


@dataclass(frozen=True)
@total_ordering
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

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, InvalidRowSpecification):
            return NotImplemented
        return (self.sheet_name, self.row, self.column) < (other.sheet_name, other.row, other.column)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, InvalidRowSpecification):
            return NotImplemented
        return (self.sheet_name, self.row, self.column) == (other.sheet_name, other.row, other.column)

    @classmethod
    def from_pydantic_error(
        cls, error: ErrorDetails, read_info_by_sheet: dict[str, SpreadsheetRead] | None = None
    ) -> Self:
        sheet_name, _, row, column, *__ = error["loc"]
        reader = (read_info_by_sheet or {}).get(str(sheet_name), SpreadsheetRead())
        return cls(
            column=str(column),
            row=reader.adjusted_row_number(int(row)),
            type=error["type"],
            msg=error["msg"],
            input=error.get("input"),
            url=str(url) if (url := error.get("url")) else None,
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["sheet_name"] = self.sheet_name
        output["column"] = self.column
        output["row"] = self.row
        output["type"] = self.type
        output["msg"] = self.msg
        output["input"] = self.input
        output["url"] = self.url
        return output

    def message(self) -> str:
        input_str = str(self.input) if self.input is not None else ""
        input_str = input_str[:50] + "..." if len(input_str) > 50 else input_str
        output = (
            f"In {self.sheet_name}, row={self.row}, column={self.column}: {self.msg}. "
            f"[type={self.type}, input_value={input_str}]"
        )
        if self.url:
            output += f" For further information visit {self.url}"
        return output


@dataclass(frozen=True)
class InvalidPropertySpecification(InvalidRowSpecification):
    sheet_name = "Properties"


@dataclass(frozen=True)
class InvalidClassSpecification(InvalidRowSpecification):
    sheet_name = "Classes"


@dataclass(frozen=True)
class InvalidContainerSpecification(InvalidRowSpecification):
    sheet_name = "Containers"


@dataclass(frozen=True)
class InvalidViewSpecification(InvalidRowSpecification):
    sheet_name = "Views"


@dataclass(frozen=True)
class InvalidRowSpecificationUnknownSheet(InvalidRowSpecification):
    sheet_name = "Unknown"

    actual_sheet_name: str

    @classmethod
    def from_pydantic_error(
        cls, error: ErrorDetails, read_info_by_sheet: dict[str, SpreadsheetRead] | None = None
    ) -> Self:
        sheet_name, _, row, column, *__ = error["loc"]
        reader = (read_info_by_sheet or {}).get(str(sheet_name), SpreadsheetRead())
        return cls(
            column=str(column),
            row=reader.adjusted_row_number(int(row)),
            actual_sheet_name=str(sheet_name),
            type=error["type"],
            msg=error["msg"],
            input=error.get("input"),
            url=str(url) if (url := error.get("url")) else None,
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["actual_sheet_name"] = self.actual_sheet_name
        return output


_INVALID_SPECIFICATION_BY_SHEET_NAME = {
    cls_.sheet_name: cls_ for cls_ in InvalidRowSpecification.__subclasses__() if cls_ is not InvalidRowSpecification
}
