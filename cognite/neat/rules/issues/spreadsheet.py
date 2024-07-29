import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import total_ordering
from typing import Any, ClassVar

from pydantic_core import ErrorDetails

from cognite.neat.issues import MultiValueError, NeatError
from cognite.neat.issues.errors.resources import MultiplePropertyDefinitionsError, ResourceNotDefinedError
from cognite.neat.utils.spreadsheet import SpreadsheetRead

from .base import DefaultPydanticError, NeatValidationError

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


@dataclass(frozen=True)
class InvalidSheetError(NeatValidationError, ABC):
    @classmethod
    @abstractmethod
    def from_pydantic_error(
        cls,
        error: ErrorDetails,
        read_info_by_sheet: dict[str, SpreadsheetRead] | None = None,
    ) -> Self:
        raise NotImplementedError

    @classmethod
    def from_pydantic_errors(
        cls,
        errors: list[ErrorDetails],
        read_info_by_sheet: dict[str, SpreadsheetRead] | None = None,
        **kwargs: Any,
    ) -> "list[NeatError]":
        output: list[NeatError] = []
        for error in errors:
            if raised_error := error.get("ctx", {}).get("error"):
                if isinstance(raised_error, MultiValueError):
                    for caught_error in raised_error.errors:
                        reader = (read_info_by_sheet or {}).get("Properties", SpreadsheetRead())
                        if (
                            isinstance(caught_error, MultiplePropertyDefinitionsError)
                            and caught_error.location_name == "rows"
                        ):
                            adjusted_row_number = tuple(
                                reader.adjusted_row_number(row_no) if isinstance(row_no, int) else row_no
                                for row_no in caught_error.locations
                            )
                            # The error is frozen, so we have to use __setattr__ to change the row number
                            object.__setattr__(caught_error, "locations", adjusted_row_number)
                        if isinstance(caught_error, InvalidRowError):
                            # Adjusting the row number to the actual row number in the spreadsheet
                            new_row = reader.adjusted_row_number(caught_error.row)
                            # The error is frozen, so we have to use __setattr__ to change the row number
                            object.__setattr__(caught_error, "row", new_row)
                        output.append(caught_error)  # type: ignore[arg-type]
                        if isinstance(caught_error, ResourceNotDefinedError):
                            if isinstance(caught_error.row_number, int) and caught_error.sheet_name == "Properties":
                                new_row = reader.adjusted_row_number(caught_error.row_number)
                                object.__setattr__(caught_error, "row_number", new_row)
                    continue

            if len(error["loc"]) >= 4:
                sheet_name, *_ = error["loc"]
                error_cls = _INVALID_ROW_ERROR_BY_SHEET_NAME.get(str(sheet_name), InvalidRowUnknownSheetError)
                output.append(error_cls.from_pydantic_error(error, read_info_by_sheet))
                continue

            output.append(DefaultPydanticError.from_pydantic_error(error))
        return output


@dataclass(frozen=True)
@total_ordering
class InvalidRowError(InvalidSheetError, ABC):
    description: ClassVar[str] = "This is a generic class for all invalid row specifications."
    fix: ClassVar[str] = "Follow the instruction in the error message."
    sheet_name: ClassVar[str]

    column: str
    row: int
    type: str
    msg: str
    input: Any
    url: str | None

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, InvalidRowError):
            return NotImplemented
        return (self.sheet_name, self.row, self.column) < (
            other.sheet_name,
            other.row,
            other.column,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, InvalidRowError):
            return NotImplemented
        return (self.sheet_name, self.row, self.column) == (
            other.sheet_name,
            other.row,
            other.column,
        )

    @classmethod
    def from_pydantic_error(
        cls,
        error: ErrorDetails,
        read_info_by_sheet: dict[str, SpreadsheetRead] | None = None,
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
class InvalidPropertyError(InvalidRowError):
    sheet_name = "Properties"


@dataclass(frozen=True)
class InvalidClassError(InvalidRowError):
    sheet_name = "Classes"


@dataclass(frozen=True)
class InvalidContainerError(InvalidRowError):
    sheet_name = "Containers"


@dataclass(frozen=True)
class InvalidViewError(InvalidRowError):
    sheet_name = "Views"


@dataclass(frozen=True)
class InvalidRowUnknownSheetError(InvalidRowError):
    sheet_name = "Unknown"

    actual_sheet_name: str

    @classmethod
    def from_pydantic_error(
        cls,
        error: ErrorDetails,
        read_info_by_sheet: dict[str, SpreadsheetRead] | None = None,
    ) -> Self:
        sheet_name, _, row, column, *__ = error["loc"]
        reader = (read_info_by_sheet or {}).get(str(sheet_name), SpreadsheetRead())
        try:
            return cls(
                column=str(column),
                row=reader.adjusted_row_number(int(row)),
                actual_sheet_name=str(sheet_name),
                type=error["type"],
                msg=error["msg"],
                input=error.get("input"),
                url=str(url) if (url := error.get("url")) else None,
            )
        except ValueError:
            return DefaultPydanticError.from_pydantic_error(error)  # type: ignore[return-value]

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["actual_sheet_name"] = self.actual_sheet_name
        return output


_INVALID_ROW_ERROR_BY_SHEET_NAME = {
    cls_.sheet_name: cls_ for cls_ in InvalidRowError.__subclasses__() if cls_ is not InvalidRowError
}


@dataclass(frozen=True)
class PropertiesDefinedForUndefinedClassesError(NeatValidationError):
    description = "Properties are defined for undefined classes."
    fix = "Make sure to define class in the Classes sheet."

    classes: list[str]

    def dump(self) -> dict[str, list[str]]:
        output = super().dump()
        output["classes"] = self.classes
        return output

    def message(self) -> str:
        return (
            f"Classes {', '.join(self.classes)} have properties assigned to them, but"
            " they are not defined in the Classes sheet."
        )
