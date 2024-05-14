import logging
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Generic, Literal, TypeVar, overload

from cognite.client import CogniteClient
from pydantic_core import ErrorDetails

from cognite.neat.legacy.graph.models import Triple
from cognite.neat.legacy.graph.stores import NeatGraphStoreBase
from cognite.neat.legacy.graph.transformations.query_generator.sparql import build_construct_query
from cognite.neat.legacy.rules.models import Rules

T_Output = TypeVar("T_Output")


class BaseLoader(ABC, Generic[T_Output]):
    """Base class for all loaders.

    A loader is a class that loads data from a source graph into
    target outside Neat.
    """

    def __init__(self, rules: Rules, graph_store: NeatGraphStoreBase):
        self.rules = rules
        self.graph_store = graph_store

    @overload
    def load(self, stop_on_exception: Literal[True]) -> Iterable[T_Output]: ...

    @overload
    def load(self, stop_on_exception: Literal[False] = False) -> Iterable[T_Output | ErrorDetails]: ...

    @abstractmethod
    def load(self, stop_on_exception: bool = False) -> Iterable[T_Output | ErrorDetails]:
        """Load the graph with data."""
        pass

    def _iterate_class_triples(self, exclude_classes: set[str] | None = None) -> Iterable[tuple[str, Iterable[Triple]]]:
        """Iterate over all classes and their triples."""
        for class_name in self.rules.classes:
            if exclude_classes is not None and class_name in exclude_classes:
                continue
            try:
                sparql_construct_query = build_construct_query(
                    self.graph_store.graph, class_name, self.rules, properties_optional=True
                )
            except Exception as e:
                logging.error(f"Failed to build construct query for class {class_name}: {e}")
                continue

            yield class_name, self.graph_store.query_delayed(sparql_construct_query)


class CogniteLoader(BaseLoader[T_Output], ABC):
    """Base class for all loaders.

    A loader is a class that loads data from a source graph into
    target outside Neat.
    """

    @abstractmethod
    def load_to_cdf(
        self, client: CogniteClient, batch_size: int | None = 1000, max_retries: int = 1, retry_delay: int = 3
    ) -> None:
        """Load the graph with data."""
        pass
