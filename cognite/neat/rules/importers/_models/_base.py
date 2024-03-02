from abc import ABC
from collections import UserList
from dataclasses import dataclass
from typing import ClassVar


@dataclass
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


@dataclass
class ValidationError(ValidationIssue, ABC):
    ...


@dataclass
class ValidationWarning(ValidationIssue, ABC):
    ...


class IssueList(UserList[ValidationIssue]):
    def as_errors(self) -> ExceptionGroup:
        raise NotImplementedError()
