import inspect
import sys
import warnings
from abc import ABC
from collections.abc import Collection, Hashable, Iterable, Sequence
from dataclasses import dataclass, fields
from functools import total_ordering
from pathlib import Path
from types import UnionType
from typing import Any, ClassVar, Literal, TypeAlias, TypeVar, get_args, get_origin
from warnings import WarningMessage

import pandas as pd
from cognite.client.data_classes.data_modeling import (
    ContainerId,
    DataModelId,
    PropertyId,
    ViewId,
)
from pydantic_core import ErrorDetails

from cognite.neat._utils.spreadsheet import SpreadsheetRead
from cognite.neat._utils.text import humanize_collection, to_camel, to_snake

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

T_Identifier = TypeVar("T_Identifier", bound=Hashable)

T_ReferenceIdentifier = TypeVar("T_ReferenceIdentifier", bound=Hashable)

ResourceType: TypeAlias = (
    Literal[
        "view",
        "container",
        "view property",
        "container property",
        "space",
        "class",
        "property",
        "asset",
        "relationship",
        "data model",
        "edge",
        "node",
        "enum collection",
        "unknown",
    ]
    # String to handle all unknown types in different importers.
    | str
)


@total_ordering
@dataclass(unsafe_hash=True)
class NeatIssue:
    """This is the base class for all exceptions and warnings (issues) used in Neat."""

    extra: ClassVar[str | None] = None
    fix: ClassVar[str | None] = None

    def as_message(self, include_type: bool = True) -> str:
        """Return a human-readable message for the issue."""
        template = self.__doc__
        if not template:
            return "Missing"
        variables, has_all_optional = self._get_variables()

        msg = template.format(**variables)
        if self.extra and has_all_optional:
            msg += "\n" + self.extra.format(**variables)
        if self.fix:
            msg += f"\nFix: {self.fix.format(**variables)}"
        if include_type:
            name = type(self).__name__
            msg = f"{name}: {msg}"
        return msg

    def _get_variables(self) -> tuple[dict[str, str], bool]:
        variables: dict[str, str] = {}
        has_all_optional = True
        for name, var_ in vars(self).items():
            if var_ is None:
                has_all_optional = False
            elif isinstance(var_, str):
                variables[name] = var_
            elif isinstance(var_, Path):
                variables[name] = var_.as_posix()
            elif isinstance(var_, Collection):
                variables[name] = humanize_collection(var_)
            else:
                variables[name] = repr(var_)
        return variables, has_all_optional

    def dump(self) -> dict[str, Any]:
        """Return a dictionary representation of the issue."""
        variables = vars(self)
        output = {to_camel(key): self._dump_value(value) for key, value in variables.items() if value is not None}
        output["NeatIssue"] = type(self).__name__
        return output

    @classmethod
    def _dump_value(cls, value: Any) -> list | int | bool | float | str | dict:
        from cognite.neat._rules.models.entities import Entity

        if isinstance(value, str | int | bool | float):
            return value
        elif isinstance(value, frozenset):
            return [cls._dump_value(item) for item in value]
        elif isinstance(value, Path):
            return value.as_posix()
        elif isinstance(value, tuple):
            return [cls._dump_value(item) for item in value]
        elif isinstance(value, ViewId | ContainerId):
            return value.dump(camel_case=True, include_type=True)
        elif isinstance(value, Entity):
            return value.dump()
        elif isinstance(value, PropertyId):
            return value.dump(camel_case=True)
        elif isinstance(value, DataModelId):
            return value.dump(camel_case=True, include_type=False)
        raise ValueError(f"Unsupported type: {type(value)}")

    @classmethod
    def load(cls, data: dict[str, Any]) -> "NeatIssue":
        """Create an instance of the issue from a dictionary."""
        from cognite.neat._issues.errors import _NEAT_ERRORS_BY_NAME, NeatValueError
        from cognite.neat._issues.warnings import _NEAT_WARNINGS_BY_NAME

        if "NeatIssue" not in data:
            raise NeatValueError("The data does not contain a NeatIssue key.")
        issue_type = data.pop("NeatIssue")
        args = {to_snake(key): value for key, value in data.items()}
        if issue_type in _NEAT_ERRORS_BY_NAME:
            return cls._load_values(_NEAT_ERRORS_BY_NAME[issue_type], args)
        elif issue_type in _NEAT_WARNINGS_BY_NAME:
            return cls._load_values(_NEAT_WARNINGS_BY_NAME[issue_type], args)
        else:
            raise NeatValueError(f"Unknown issue type: {issue_type}")

    @classmethod
    def _load_values(cls, neat_issue_cls: "type[NeatIssue]", data: dict[str, Any]) -> "NeatIssue":
        args: dict[str, Any] = {}
        for f in fields(neat_issue_cls):
            if f.name not in data:
                continue
            value = data[f.name]
            args[f.name] = cls._load_value(f.type, value)
        return neat_issue_cls(**args)

    @classmethod
    def _load_value(cls, type_: Any, value: Any) -> Any:
        from cognite.neat._rules.models.entities import Entity

        if isinstance(type_, UnionType) or get_origin(type_) is UnionType:
            args = get_args(type_)
            return cls._load_value(args[0], value)
        elif type_ is frozenset or get_origin(type_) is frozenset:
            subtype = get_args(type_)[0]
            return frozenset(cls._load_value(subtype, item) for item in value)
        elif type_ is Path:
            return Path(value)
        elif type_ is tuple or get_origin(type_) is tuple:
            subtype = get_args(type_)[0]
            return tuple(cls._load_value(subtype, item) for item in value)
        elif type_ is ViewId:
            return ViewId.load(value)
        elif type_ is DataModelId:
            return DataModelId.load(value)
        elif type_ is PropertyId:
            return PropertyId.load(value)
        elif type_ is ContainerId:
            return ContainerId.load(value)
        elif inspect.isclass(type_) and issubclass(type_, Entity):
            return type_.load(value)
        return value

    def __lt__(self, other: "NeatIssue") -> bool:
        if not isinstance(other, NeatIssue):
            return NotImplemented
        return (type(self).__name__, self.as_message()) < (type(other).__name__, other.as_message())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NeatIssue):
            return NotImplemented
        return (type(self).__name__, self.as_message()) == (type(other).__name__, other.as_message())


@dataclass(unsafe_hash=True)
class NeatError(NeatIssue, Exception):
    """This is the base class for all exceptions (errors) used in Neat."""

    @classmethod
    def from_pydantic_errors(cls, errors: list[ErrorDetails], **kwargs) -> "list[NeatError]":
        """Convert a list of pydantic errors to a list of Error instances.

        This is intended to be overridden in subclasses to handle specific error types.
        """
        all_errors: list[NeatError] = []
        read_info_by_sheet = kwargs.get("read_info_by_sheet")

        for error in errors:
            if error["type"] == "is_instance_of" and error["loc"][1] == "is-instance[SheetList]":
                # Skip the error for SheetList, as it is not relevant for the user. This is an
                # internal class used to have helper methods for a lists as .to_pandas()
                continue
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
                all_errors.append(RowError.from_pydantic_error(error, read_info_by_sheet))
            else:
                all_errors.append(DefaultPydanticError.from_pydantic_error(error))
        return all_errors

    @staticmethod
    def _adjust_row_numbers(caught_error: "NeatError", read_info_by_sheet: dict[str, SpreadsheetRead]) -> None:
        from cognite.neat._issues.errors._properties import PropertyDefinitionDuplicatedError
        from cognite.neat._issues.errors._resources import ResourceNotDefinedError

        reader = read_info_by_sheet.get("Properties", SpreadsheetRead())

        if isinstance(caught_error, PropertyDefinitionDuplicatedError) and caught_error.location_name == "rows":
            adjusted_row_number = (
                tuple(
                    reader.adjusted_row_number(row_no) if isinstance(row_no, int) else row_no
                    for row_no in caught_error.locations or []
                )
                or None
            )
            # The error is frozen, so we have to use __setattr__ to change the row number
            object.__setattr__(caught_error, "locations", adjusted_row_number)
        elif isinstance(caught_error, RowError):
            # Adjusting the row number to the actual row number in the spreadsheet
            new_row = reader.adjusted_row_number(caught_error.row)
            # The error is frozen, so we have to use __setattr__ to change the row number
            object.__setattr__(caught_error, "row", new_row)
        elif isinstance(caught_error, ResourceNotDefinedError):
            if isinstance(caught_error.row_number, int) and caught_error.sheet_name == "Properties":
                new_row = reader.adjusted_row_number(caught_error.row_number)
                object.__setattr__(caught_error, "row_number", new_row)


@dataclass(unsafe_hash=True)
class DefaultPydanticError(NeatError, ValueError):
    """{type}: {msg} [loc={loc}]"""

    type: str
    loc: tuple[int | str, ...]
    msg: str

    @classmethod
    def from_pydantic_error(cls, error: ErrorDetails) -> "DefaultPydanticError":
        return cls(
            type=error["type"],
            loc=error["loc"],
            msg=error["msg"],
        )

    def as_message(self, include_type: bool = True) -> str:
        if self.loc and len(self.loc) == 1:
            return f"{self.loc[0]} sheet: {self.msg}"
        elif self.loc and len(self.loc) == 2:
            return f"{self.loc[0]} sheet field/column <{self.loc[1]}>: {self.msg}"
        else:
            return self.msg


@dataclass(unsafe_hash=True)
class RowError(NeatError, ValueError):
    """In {sheet_name}, row={row}, column={column}: {msg}. [type={type}, input_value={input}]"""

    extra = "For further information visit {url}"

    sheet_name: str
    column: str
    row: int
    type: str
    msg: str
    input: Any
    url: str | None = None

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

    def as_message(self, include_type: bool = True) -> str:
        input_str = str(self.input) if self.input is not None else ""
        input_str = input_str[:50] + "..." if len(input_str) > 50 else input_str
        output = (
            f"In {self.sheet_name}, row={self.row}, column={self.column}: {self.msg}. "
            f"[type={self.type}, input_value={input_str}]"
        )
        if self.url:
            output += f" For further information visit {self.url}"
        return output


@dataclass(unsafe_hash=True)
class NeatWarning(NeatIssue, UserWarning):
    """This is the base class for all warnings used in Neat."""

    @classmethod
    def from_warning(cls, warning: WarningMessage) -> "NeatWarning":
        """Create a NeatWarning from a WarningMessage."""
        return DefaultWarning.from_warning_message(warning)


@dataclass(unsafe_hash=True)
class DefaultWarning(NeatWarning):
    """{category}: {warning}"""

    extra = "Source: {source}"

    warning: str
    category: str
    source: str | None = None

    @classmethod
    def from_warning_message(cls, warning: WarningMessage) -> NeatWarning:
        if isinstance(warning.message, NeatWarning):
            return warning.message

        return cls(
            warning=str(warning.message),
            category=warning.category.__name__,
            source=warning.source,
        )

    def as_message(self, include_type: bool = True) -> str:
        return str(self.warning)


T_NeatIssue = TypeVar("T_NeatIssue", bound=NeatIssue)


class NeatIssueList(list, Sequence[T_NeatIssue], ABC):
    """This is a generic list of NeatIssues."""

    def __init__(self, issues: Sequence[T_NeatIssue] | None = None, title: str | None = None):
        super().__init__(issues or [])
        self.title = title

    @property
    def errors(self) -> Self:
        """Return all the errors in this list."""
        return type(self)([issue for issue in self if isinstance(issue, NeatError)])  # type: ignore[misc]

    @property
    def has_errors(self) -> bool:
        """Return True if this list contains any errors."""
        return any(isinstance(issue, NeatError) for issue in self)

    @property
    def warnings(self) -> Self:
        """Return all the warnings in this list."""
        return type(self)([issue for issue in self if isinstance(issue, NeatWarning)])  # type: ignore[misc]

    def as_errors(self, operation: str = "Operation failed") -> ExceptionGroup:
        """Return an ExceptionGroup with all the errors in this list."""
        return ExceptionGroup(
            operation,
            [issue for issue in self if isinstance(issue, NeatError)],
        )

    def trigger_warnings(self) -> None:
        """Trigger all warnings in this list."""
        for warning in [issue for issue in self if isinstance(issue, NeatWarning)]:
            warnings.warn(warning, stacklevel=2)

    def to_pandas(self) -> pd.DataFrame:
        """Return a pandas DataFrame representation of this list."""
        return pd.DataFrame([issue.dump() for issue in self])

    def _repr_html_(self) -> str | None:
        return self.to_pandas()._repr_html_()  # type: ignore[operator]

    def as_exception(self) -> "MultiValueError":
        """Return a MultiValueError with all the errors in this list."""
        return MultiValueError(self.errors)


class MultiValueError(ValueError):
    """This is a container for multiple errors.

    It is used in the pydantic field_validator/model_validator to collect multiple errors, which
    can then be caught in a try-except block and returned as an IssueList.

    """

    def __init__(self, errors: Sequence[NeatIssue]):
        self.errors = list(errors)


class IssueList(NeatIssueList[NeatIssue]):
    """This is a list of NeatIssues."""

    def _repr_html_(self) -> str | None:
        if not self:
            return "<p>'No issues found'</p>"
        df = self.to_pandas()
        agg_df = df["NeatIssue"].value_counts().to_frame()
        if len(agg_df) < 10:
            return agg_df._repr_html_()  # type: ignore[operator]
        else:
            return agg_df.head()._repr_html_()  # type: ignore[operator]


T_Cls = TypeVar("T_Cls")


def _get_subclasses(cls_: type[T_Cls], include_base: bool = False) -> Iterable[type[T_Cls]]:
    """Get all subclasses of a class."""
    if include_base:
        yield cls_
    for s in cls_.__subclasses__():
        yield s
        yield from _get_subclasses(s, False)
