import sys
import warnings
from abc import ABC, abstractmethod
from collections import UserList
from collections.abc import Sequence
from dataclasses import dataclass
from functools import total_ordering
from typing import Any, ClassVar, TypeVar
from warnings import WarningMessage

import pandas as pd
from pydantic_core import ErrorDetails, PydanticCustomError

from cognite.neat.utils.spreadsheet import SpreadsheetRead

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup
    from typing_extensions import Self
else:
    from typing import Self


__all__ = [
    "NeatIssue",
    "NeatError",
    "NeatWarning",
    "DefaultWarning",
    "NeatIssueList",
    "MultiValueError",
]


@total_ordering
@dataclass(frozen=True)
class NeatIssue(ABC):
    """This is the base class for all exceptions and warnings (issues) used in Neat."""

    description: ClassVar[str]
    extra: ClassVar[str | None] = None
    fix: ClassVar[str | None] = None

    def message(self) -> str:
        """Return a human-readable message for the issue.

        This is the default implementation, which returns the description.
        It is recommended to override this method in subclasses with a more
        specific message.
        """
        return self.__doc__ or "Missing"

    @abstractmethod
    def dump(self) -> dict[str, Any]:
        """Return a dictionary representation of the issue."""
        raise NotImplementedError()

    def __lt__(self, other: "NeatIssue") -> bool:
        if not isinstance(other, NeatIssue):
            return NotImplemented
        return (type(self).__name__, self.message()) < (type(other).__name__, other.message())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NeatIssue):
            return NotImplemented
        return (type(self).__name__, self.message()) == (type(other).__name__, other.message())


@dataclass(frozen=True)
class NeatError(NeatIssue, ABC):
    def dump(self) -> dict[str, Any]:
        return {"errorType": type(self).__name__}

    def as_exception(self) -> Exception:
        return ValueError(self.message())

    def as_pydantic_exception(self) -> PydanticCustomError:
        return PydanticCustomError(
            type(self).__name__,
            self.message(),
            dict(description=self.__doc__, fix=self.fix),
        )

    @classmethod
    def from_pydantic_errors(cls, errors: list[ErrorDetails], **kwargs) -> "list[NeatError]":
        """Convert a list of pydantic errors to a list of Error instances.

        This is intended to be overridden in subclasses to handle specific error types.
        """
        all_errors: list[NeatError] = []
        read_info_by_sheet = kwargs.get("read_info_by_sheet")

        for error in errors:
            ctx = error.get("ctx")
            if isinstance(ctx, dict) and isinstance(multi_error := ctx.get("error"), MultiValueError):
                if read_info_by_sheet:
                    for caught_error in multi_error.errors:
                        cls._adjust_row_numbers(caught_error, read_info_by_sheet)  # type: ignore[arg-type]
                all_errors.extend(multi_error.errors)  # type: ignore[arg-type]
            elif isinstance(ctx, dict) and isinstance(single_error := ctx.get("error"), NeatError):
                if read_info_by_sheet:
                    cls._adjust_row_numbers(single_error, read_info_by_sheet)
                all_errors.append(single_error)
            elif len(error["loc"]) >= 4 and read_info_by_sheet:
                all_errors.append(InvalidRowError.from_pydantic_error(error, read_info_by_sheet))
            else:
                all_errors.append(DefaultPydanticError.from_pydantic_error(error))
        return all_errors

    @staticmethod
    def _adjust_row_numbers(caught_error: "NeatError", read_info_by_sheet: dict[str, SpreadsheetRead]) -> None:
        from cognite.neat.issues.errors.resources import MultiplePropertyDefinitionsError, ResourceNotDefinedError

        reader = read_info_by_sheet.get("Properties", SpreadsheetRead())

        if isinstance(caught_error, MultiplePropertyDefinitionsError) and caught_error.location_name == "rows":
            adjusted_row_number = tuple(
                reader.adjusted_row_number(row_no) if isinstance(row_no, int) else row_no
                for row_no in caught_error.locations
            )
            # The error is frozen, so we have to use __setattr__ to change the row number
            object.__setattr__(caught_error, "locations", adjusted_row_number)
        elif isinstance(caught_error, InvalidRowError):
            # Adjusting the row number to the actual row number in the spreadsheet
            new_row = reader.adjusted_row_number(caught_error.row)
            # The error is frozen, so we have to use __setattr__ to change the row number
            object.__setattr__(caught_error, "row", new_row)
        elif isinstance(caught_error, ResourceNotDefinedError):
            if isinstance(caught_error.row_number, int) and caught_error.sheet_name == "Properties":
                new_row = reader.adjusted_row_number(caught_error.row_number)
                object.__setattr__(caught_error, "row_number", new_row)


@dataclass(frozen=True)
class DefaultPydanticError(NeatError):
    type: str
    loc: tuple[int | str, ...]
    msg: str
    input: Any
    ctx: dict[str, Any] | None

    @classmethod
    def from_pydantic_error(cls, error: ErrorDetails) -> "DefaultPydanticError":
        return cls(
            type=error["type"],
            loc=error["loc"],
            msg=error["msg"],
            input=error.get("input"),
            ctx=error.get("ctx"),
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["type"] = self.type
        output["loc"] = self.loc
        output["msg"] = self.msg
        output["input"] = self.input
        output["ctx"] = self.ctx
        return output

    def message(self) -> str:
        if self.loc and len(self.loc) == 1:
            return f"{self.loc[0]} sheet: {self.msg}"
        elif self.loc and len(self.loc) == 2:
            return f"{self.loc[0]} sheet field/column <{self.loc[1]}>: {self.msg}"
        else:
            return self.msg


@dataclass(frozen=True)
class InvalidRowError(NeatError):
    sheet_name: str
    column: str
    row: int
    type: str
    msg: str
    input: Any
    url: str | None

    @classmethod
    def from_pydantic_error(
        cls,
        error: ErrorDetails,
        read_info_by_sheet: dict[str, SpreadsheetRead] | None = None,
    ) -> Self:
        sheet_name, _, row, column, *__ = error["loc"]
        reader = (read_info_by_sheet or {}).get(str(sheet_name), SpreadsheetRead())
        return cls(
            sheet_name=str(sheet_name),
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
class NeatWarning(NeatIssue, ABC, UserWarning):
    def dump(self) -> dict[str, Any]:
        return {"warningType": type(self).__name__}

    @classmethod
    def from_warning(cls, warning: WarningMessage) -> "NeatWarning":
        return DefaultWarning.from_warning_message(warning)


@dataclass(frozen=True)
class DefaultWarning(NeatWarning):
    description = "A warning was raised during validation."
    fix = "No fix is available."

    warning: str | Warning
    category: type[Warning]
    source: str | None = None

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["msg"] = str(self.warning)
        output["category"] = self.category.__name__
        output["source"] = self.source
        return output

    @classmethod
    def from_warning_message(cls, warning: WarningMessage) -> NeatWarning:
        if isinstance(warning.message, NeatWarning):
            return warning.message

        return cls(
            warning=warning.message,
            category=warning.category,
            source=warning.source,
        )

    def message(self) -> str:
        return str(self.warning)


T_NeatIssue = TypeVar("T_NeatIssue", bound=NeatIssue)


class NeatIssueList(UserList[T_NeatIssue], ABC):
    def __init__(self, issues: Sequence[T_NeatIssue] | None = None, title: str | None = None):
        super().__init__(issues or [])
        self.title = title

    @property
    def errors(self) -> Self:
        return type(self)([issue for issue in self if isinstance(issue, NeatError)])  # type: ignore[misc]

    @property
    def has_errors(self) -> bool:
        return any(isinstance(issue, NeatError) for issue in self)

    @property
    def warnings(self) -> Self:
        return type(self)([issue for issue in self if isinstance(issue, NeatWarning)])  # type: ignore[misc]

    def as_errors(self) -> ExceptionGroup:
        return ExceptionGroup(
            "Operation failed",
            [ValueError(issue.message()) for issue in self if isinstance(issue, NeatError)],
        )

    def trigger_warnings(self) -> None:
        for warning in [issue for issue in self if isinstance(issue, NeatWarning)]:
            warnings.warn(warning, stacklevel=2)

    def to_pandas(self) -> pd.DataFrame:
        return pd.DataFrame([issue.dump() for issue in self])

    def _repr_html_(self) -> str | None:
        return self.to_pandas()._repr_html_()  # type: ignore[operator]

    def as_exception(self) -> "MultiValueError":
        return MultiValueError(self.errors)


class MultiValueError(ValueError):
    """This is a container for multiple errors.

    It is used in the pydantic field_validator/model_validator to collect multiple errors, which
    can then be caught in a try-except block and returned as an IssueList.

    """

    def __init__(self, errors: Sequence[NeatIssue]):
        self.errors = list(errors)


class IssueList(NeatIssueList[NeatIssue]): ...
