from abc import ABC, abstractmethod

from rdflib import Graph


class RuleTransformer(ABC):
    @abstractmethod
    def transform(self, graph: Graph) -> None:
        raise NotImplementedError()
