from abc import ABC
from collections import UserList
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class ValidationIssue(ABC):
    description: ClassVar[str]
    fix: ClassVar[str]


@dataclass
class ValidationError(ValidationIssue, ABC):
    ...


@dataclass
class ValidationWarning(ValidationIssue, ABC):
    ...


class IssueList(UserList[ValidationIssue]):
    def as_errors(self) -> ExceptionGroup:
        raise NotImplementedError()
