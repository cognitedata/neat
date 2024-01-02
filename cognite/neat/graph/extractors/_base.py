from abc import abstractmethod
from collections.abc import Iterable


class BaseExtractor:
    """This is the base class for all extractors. It defines the interface that
    extractors must implement.
    """

    @abstractmethod
    def extract(self) -> Iterable[tuple]:
        raise NotImplementedError()
