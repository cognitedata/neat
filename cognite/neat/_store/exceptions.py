"""These are special exceptions that are used by the store to signal invalid transformers"""

from dataclasses import dataclass
from ._provenance import Activity
from cognite.neat._issues import IssueList


class NeatStoreError(Exception):
    """Base class for all exceptions in the store module"""
    def __str__(self):
        return type(self).__name__

class ActivityFailed(NeatStoreError):
    """Raised when an activity fails"""

    def __init__(self, activity: Activity, issue_list: IssueList) -> None:
        self.activity = activity
        self.issue_list = issue_list

    def __str__(self):
        return f"{super().__str__()}: {self.activity.id_}"

class InvalidActivityOutput(NeatStoreError):
    """Raised when an activity has an invalid output"""

    def __init__(self, activity: Activity, output: str) -> None:
        self.activity = activity
        self.output = output

    def __str__(self):
        return f"{super().__str__()}: {self.activity.id_} -> {self.output}"



@dataclass
class InvalidInputOperation(NeatStoreError, RuntimeError):
    """Raised when an invalid operation is attempted"""

    expected: tuple[type, ...]
    have: tuple[type, ...]


class EmptyStore(NeatStoreError, RuntimeError):
    """Raised when the store is empty"""

    ...
