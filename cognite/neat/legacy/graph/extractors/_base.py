from abc import abstractmethod
from collections.abc import Iterable

from cognite.neat.legacy.graph.models import Triple


class BaseExtractor:
    """This is the base class for all extractors. It defines the interface that
    extractors must implement.
    """

    @abstractmethod
    def extract(self) -> Iterable[Triple]:
        raise NotImplementedError()
