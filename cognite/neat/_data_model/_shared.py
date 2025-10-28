from abc import ABC, abstractmethod
from typing import Any

from cognite.neat._client.client import NeatClient


class OnSuccess(ABC):
    """Abstract base class for post-activity success handlers."""

    def __init__(self, client: NeatClient | None = None) -> None:
        self._client = client
        self.issues: list = []

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
