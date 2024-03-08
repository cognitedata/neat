import sys
from abc import ABC, abstractmethod
from collections import UserList
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, ClassVar
from warnings import WarningMessage

import pandas as pd
from pydantic_core import ErrorDetails

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup
else:
    pass


@dataclass(order=True, frozen=True)
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


@dataclass(frozen=True, order=True)
class Error(ValidationIssue, ABC):
    def dump(self) -> dict[str, Any]:
        return {"error": type(self).__name__}

    @classmethod
    def from_pydantic_errors(cls, errors: list[ErrorDetails], **kwargs) -> "list[Error]":
        """Convert a list of pydantic errors to a list of Error instances.

        This is intended to be overridden in subclasses to handle specific error types.
        """
        return [DefaultPydanticError.from_pydantic_error(error) for error in errors]


@dataclass(frozen=True, order=True)
class DefaultPydanticError(Error):
    type: str
    loc: tuple[int | str, ...]
    msg: str
    input: Any
    ctx: dict[str, Any] | None

    @classmethod
    def from_pydantic_error(cls, error: ErrorDetails) -> "Error":
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
        return self.msg


@dataclass(frozen=True, order=True)
class ValidationWarning(ValidationIssue, ABC, UserWarning):
    def dump(self) -> dict[str, Any]:
        return {"warning": type(self).__name__}

    @classmethod
    def from_warning(cls, warning: WarningMessage) -> "ValidationWarning":
        return DefaultWarning.from_warning_message(warning)


@dataclass(frozen=True, order=True)
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

    def as_errors(self) -> ExceptionGroup:
        return ExceptionGroup(
            "Validation failed",
            [ValueError(issue.message()) for issue in self if isinstance(issue, Error)],
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

    def __init__(self, errors: Sequence[Error]):
        self.errors = list(errors)
