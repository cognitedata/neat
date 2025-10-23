from collections.abc import Sequence
from typing import TYPE_CHECKING

from ._issues import Issue

if TYPE_CHECKING:
    from cognite.neat._issues import ModelSyntaxError
    from cognite.neat._utils.http_client import HTTPMessage


class NeatException(Exception):
    """Base class for all exceptions raised by Neat."""

    pass


class NeatIssueException(NeatException):
    """Raised when there are issues detected."""

    def __init__(self, issues: Sequence[Issue]) -> None:
        self.issues = list(issues)


class DataModelImportException(NeatIssueException):
    """Raised when there is an error importing a model."""

    def __init__(self, errors: list[ModelSyntaxError]) -> None:
        super().__init__(errors)
        self.errors = errors

    def __str__(self) -> str:
        return f"Model import failed with {len(self.errors)} errors: " + "; ".join(map(str, self.errors))


class CDFAPIException(NeatException):
    """Raised when there is an error in an API call."""

    def __init__(self, messages: "list[HTTPMessage]") -> None:
        self.messages = messages
