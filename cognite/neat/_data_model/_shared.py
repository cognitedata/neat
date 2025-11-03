from abc import ABC, abstractmethod
from typing import Any

from cognite.neat._data_model.deployer.data_classes import DeploymentResult
from cognite.neat._issues import IssueList


class OnSuccess(ABC):
    """Abstract base class for post-activity success handlers."""

    @abstractmethod
    def run(self, data_model: Any) -> None:
        """Execute the success handler on the data model."""
        pass


class OnSuccessIssuesChecker(OnSuccess, ABC):
    """Abstract base class for post-activity success handlers that check for issues of the data model."""

    def __init__(self) -> None:
        self._issues = IssueList()
        self._has_run = False

    @property
    def issues(self) -> IssueList:
        if not self._has_run:
            raise RuntimeError(f"{type(self).__name__} has not been run yet.")
        return IssueList(self._issues)


class OnSuccessResultProducer(OnSuccess, ABC):
    """Abstract base class for post-activity success handlers that produce desired outcomes using the data model."""

    def __init__(self) -> None:
        self._results: DeploymentResult | None = None

    @property
    def result(self) -> DeploymentResult:
        if self._results is None:
            raise RuntimeError("SchemaDeployer has not been run yet.")
        return self._results
