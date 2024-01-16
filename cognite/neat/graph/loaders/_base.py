from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Generic, TypeVar

T_Output = TypeVar("T_Output")


class BaseLoader(ABC, Generic[T_Output]):
    """Base class for all loaders.

    A loader is a class that loads data from a source graph into
    target outside Neat.
    """

    @abstractmethod
    def load(self) -> Iterable[T_Output]:
        """Load the graph with data."""
        pass
