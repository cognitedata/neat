import sys
import warnings
from abc import ABC, abstractmethod
from collections import UserList
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from functools import total_ordering
from typing import Any, ClassVar, Literal
from warnings import WarningMessage

import pandas as pd
from pydantic import ValidationError
from pydantic_core import ErrorDetails

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup
else:
    pass

__all__ = [
    "ValidationIssue",
    "NeatValidationError",
    "DefaultPydanticError",
    "ValidationWarning",
    "DefaultWarning",
    "IssueList",
    "MultiValueError",
]


@total_ordering
@dataclass(frozen=True)
class ValidationIssue(ABC):
    description: ClassVar[str]
    fix: ClassVar[str]

    def message(self) -> str:
        """Return a human-readable message for the issue.

        This is the default implementation, which returns the description.
        It is recommended to override this method in subclasses with a more
        specific message.
        """
        return self.description

    @abstractmethod
    def dump(self) -> dict[str, Any]:
        """Return a dictionary representation of the issue."""
        raise NotImplementedError()

    def __lt__(self, other: "ValidationIssue") -> bool:
        if not isinstance(other, ValidationIssue):
            return NotImplemented
        return (type(self).__name__, self.message()) < (type(other).__name__, other.message())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ValidationIssue):
            return NotImplemented
        return (type(self).__name__, self.message()) == (type(other).__name__, other.message())


@dataclass(frozen=True)
class NeatValidationError(ValidationIssue, ABC):
    def dump(self) -> dict[str, Any]:
        return {"error": type(self).__name__}

    @classmethod
    def from_pydantic_errors(cls, errors: list[ErrorDetails], **kwargs) -> "list[NeatValidationError]":
        """Convert a list of pydantic errors to a list of Error instances.

        This is intended to be overridden in subclasses to handle specific error types.
        """
        return [DefaultPydanticError.from_pydantic_error(error) for error in errors]


@dataclass(frozen=True)
class DefaultPydanticError(NeatValidationError):
    type: str
    loc: tuple[int | str, ...]
    msg: str
    input: Any
    ctx: dict[str, Any] | None

    @classmethod
    def from_pydantic_error(cls, error: ErrorDetails) -> "NeatValidationError":
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
class ValidationWarning(ValidationIssue, ABC, UserWarning):
    def dump(self) -> dict[str, Any]:
        return {"warning": type(self).__name__}

    @classmethod
    def from_warning(cls, warning: WarningMessage) -> "ValidationWarning":
        return DefaultWarning.from_warning_message(warning)


@dataclass(frozen=True)
class DefaultWarning(ValidationWarning):
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
    def from_warning_message(cls, warning: WarningMessage) -> "ValidationWarning":
        if isinstance(warning.message, ValidationWarning):
            return warning.message

        return cls(
            warning=warning.message,
            category=warning.category,
            source=warning.source,
        )

    def message(self) -> str:
        return str(self.warning)


class IssueList(UserList[ValidationIssue]):
    def __init__(self, issues: Sequence[ValidationIssue] | None = None, title: str | None = None):
        super().__init__(issues or [])
        self.title = title

    @property
    def errors(self) -> "IssueList":
        return IssueList([issue for issue in self if isinstance(issue, NeatValidationError)])

    @property
    def has_errors(self) -> bool:
        return any(isinstance(issue, NeatValidationError) for issue in self)

    @property
    def warnings(self) -> "IssueList":
        return IssueList([issue for issue in self if isinstance(issue, ValidationWarning)])

    def as_errors(self) -> ExceptionGroup:
        return ExceptionGroup(
            "Validation failed",
            [ValueError(issue.message()) for issue in self if isinstance(issue, NeatValidationError)],
        )

    def to_pandas(self) -> pd.DataFrame:
        return pd.DataFrame([issue.dump() for issue in self])

    def _repr_html_(self) -> str | None:
        return self.to_pandas()._repr_html_()  # type: ignore[operator]


class MultiValueError(ValueError):
    """This is a container for multiple errors.

    It is used in the pydantic field_validator/model_validator to collect multiple errors, which
    can then be caught in a try-except block and returned as an IssueList.

    """

    def __init__(self, errors: Sequence[NeatValidationError]):
        self.errors = list(errors)


class _FutureResult:
    def __init__(self) -> None:
        self._result: Literal["success", "failure", "pending"] = "pending"

    @property
    def result(self) -> Literal["success", "failure", "pending"]:
        return self._result


@contextmanager
def handle_issues(
    issues: IssueList,
    error_cls: type[NeatValidationError] = NeatValidationError,
    warning_cls: type[ValidationWarning] = ValidationWarning,
    error_args: dict[str, Any] | None = None,
) -> Iterator[_FutureResult]:
    """This is an internal help function to handle issues and warnings.

    Args:
        issues: The issues list to append to.
        error_cls: The class used to convert errors to issues.
        warning_cls:  The class used to convert warnings to issues.

    Returns:
        FutureResult: A future result object that can be used to check the result of the context manager.
    """
    with warnings.catch_warnings(record=True) as warning_logger:
        warnings.simplefilter("always")
        future_result = _FutureResult()
        try:
            yield future_result
        except ValidationError as e:
            issues.extend(error_cls.from_pydantic_errors(e.errors(), **(error_args or {})))
            future_result._result = "failure"
        else:
            future_result._result = "success"
        finally:
            if warning_logger:
                issues.extend([warning_cls.from_warning(warning) for warning in warning_logger])
