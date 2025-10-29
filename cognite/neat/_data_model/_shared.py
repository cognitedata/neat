from abc import ABC, abstractmethod
from typing import Any

from cognite.neat._client.client import NeatClient
from cognite.neat._issues import IssueList


class OnSuccess(ABC):
    """Abstract base class for post-activity success handlers."""

    def __init__(self, client: NeatClient | None = None) -> None:
        self._client = client
        self._issues: IssueList = IssueList()
        self._results: list = []
        self._has_run = False

    @property
    def issues(self) -> IssueList:
        """List of issues found during the success handler execution."""
        if not self._has_run:
            raise RuntimeError("OnSuccess handler has not been run yet.")
        return self._issues

    @property
    def results(self) -> list:
        """List of results produced during the success handler execution."""
        if not self._has_run:
            raise RuntimeError("OnSuccess handler has not been run yet.")
        return self._results

    @abstractmethod
    def run(self, data_model: Any) -> None:
        """Execute the success handler on the data model."""
        pass


class OnSuccessIssuesChecker(OnSuccess):
    """Abstract base class for post-activity success handlers that check for issues of the data model."""

    ...


class OnSuccessResultProducer(OnSuccess):
    """Abstract base class for post-activity success handlers that produce desired outcomes using the data model."""

    ...
