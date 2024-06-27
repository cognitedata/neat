from abc import ABC, abstractmethod
from typing import ClassVar

from rdflib import Graph


class BaseTransformer(ABC):
    description: str
    _use_only_once: bool
    _need_changes: ClassVar[frozenset[str]] = frozenset()

    @abstractmethod
    def transform(self, graph: Graph) -> None:
        raise NotImplementedError()
