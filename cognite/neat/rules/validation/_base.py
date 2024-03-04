import sys
from abc import ABC, abstractmethod
from collections import UserList
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

import pandas as pd

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup


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


@dataclass(frozen=True, order=True)
class ValidationWarning(ValidationIssue, ABC):
    def dump(self) -> dict[str, Any]:
        return {"warning": type(self).__name__}


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
