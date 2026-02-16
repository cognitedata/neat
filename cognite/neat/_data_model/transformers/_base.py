from abc import ABC, abstractmethod
from typing import Any


class Transformer(ABC):
    """Abstract base class for data model transformers."""

    @abstractmethod
    def transform(self) -> Any:
        """Transform and return the modified data model."""
        raise NotImplementedError()
