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

    @property
    @abstractmethod
    def issues(self) -> IssueList:
        """List of issues found during the success handler execution."""
        ...


class OnSuccessResultProducer(OnSuccess, ABC):
    """Abstract base class for post-activity success handlers that produce desired outcomes using the data model."""

    @property
    @abstractmethod
    def result(self) -> DeploymentResult: ...
