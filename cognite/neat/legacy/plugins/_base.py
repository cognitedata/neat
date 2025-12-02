from abc import ABC, abstractmethod
from typing import Any


class NeatPlugin(ABC):
    @abstractmethod
    def configure(self, *args: Any, **kwargs: Any) -> Any:
        """A method that all plugins must implement."""
        raise NotImplementedError()
