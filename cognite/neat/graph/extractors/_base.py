from abc import abstractmethod
from collections.abc import Iterable

from cognite.neat.graph.models import Triple
from cognite.neat.utils.auxiliary import class_html_doc


class BaseExtractor:
    """This is the base class for all extractors. It defines the interface that
    extractors must implement.
    """

    @abstractmethod
    def extract(self) -> Iterable[Triple]:
        raise NotImplementedError()

    @classmethod
    def _repr_html_(cls) -> str:
        return class_html_doc(cls)
