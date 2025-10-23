from abc import ABC, abstractmethod
from typing import Any


class OnSuccess(ABC):
    """Abstract base class for post-activity success handlers."""

    def __init__(self, data_model: Any) -> None:
        self.data_model = data_model
        self.issues: list = []

    @abstractmethod
    def run(self) -> None:
        """Execute the success handler on the data model."""
        pass
