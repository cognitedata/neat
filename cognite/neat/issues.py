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

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup
    from typing_extensions import Self
else:
    from typing import Self


@total_ordering
@dataclass(frozen=True)
class NeatIssue(ABC):
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

    def as_exception(self) -> ValueError:
        return ValueError(self.message())


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

    def __init__(self, errors: Sequence[T_NeatIssue]):
        self.errors = list(errors)
