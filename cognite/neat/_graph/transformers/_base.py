from abc import ABC, abstractmethod
from typing import ClassVar, TypeAlias

from rdflib import Graph
from rdflib.query import ResultRow

from cognite.neat._shared import Triple
from cognite.neat._utils.collection_ import iterate_progress_bar
from cognite.neat._utils.graph_transformations_report import GraphTransformationResult
from cognite.neat._utils.rdf_ import add_triples_in_batch, remove_triples_in_batch

To_Add_Triples: TypeAlias = list[Triple]
To_Remove_Triples: TypeAlias = list[Triple]


class BaseTransformer(ABC):
    description: str
    _use_only_once: bool = False
    _need_changes: ClassVar[frozenset[str]] = frozenset()

    @abstractmethod
    def transform(self, graph: Graph) -> None:
        raise NotImplementedError()


class BaseTransformerStandardised(ABC):
    """Standardised base transformer to use in case a transformer is adding or removing triples from a graph. If you
    are doing more specialised operations, please overwrite the .transform() method.
    """

    _use_only_once: bool = False
    _need_changes: ClassVar[frozenset[str]] = frozenset()
    _use_iterate_bar_threshold: int = 500

    @abstractmethod
    def description(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    def operation(self, query_result_row: ResultRow) -> tuple[To_Add_Triples, To_Remove_Triples]:
        """The operations to perform on each row resulting from the ._iterate_query() method.
        The operation should return a list of triples to add and to remove.
        """
        raise NotImplementedError()

    @abstractmethod
    def _count_query(self) -> str:
        """
        Overwrite to fetch all affected properties in the graph as a result of the transformation.
        Returns:
            A query string.
        """
        raise NotImplementedError()

    @abstractmethod
    def _iterate_query(self) -> str:
        """
        The query to use for extracting target triples from the graph and performing the transformation.
        Returns:
            A query string.
        """
        raise NotImplementedError()

    def _skip_count_query(self) -> str:
        """
        The query to use for extracting target triples from the graph and performing the transformation.
        Returns:
            A query string.
        """
        return ""

    def transform(self, graph: Graph) -> GraphTransformationResult:
        outcome = GraphTransformationResult(self.__class__.__name__)
        to_add: list[Triple] = []
        to_remove: list[Triple] = []

        properties_count_res = list(graph.query(self._count_query()))
        properties_count = int(properties_count_res[0][0])

        outcome.affected_nodes_count = properties_count

        if self._skip_count_query():
            skipped_count_res = list(graph.query(self._count_query()))
            skipped_count = int(skipped_count_res[0][0])
            outcome.skipped = skipped_count

        if properties_count == 0:
            outcome.affected_nodes_count = 0
            return outcome

        result_iterable = graph.query(self._iterate_query())
        if properties_count > self._use_iterate_bar_threshold:
            result_iterable = iterate_progress_bar(
                result_iterable,
                total=properties_count,
                description=self.description(),
            )

        for row in result_iterable:
            triples_to_add_from_row, triples_to_remove_from_row = self.operation(row)

            to_add.extend(triples_to_add_from_row)
            to_remove.extend(triples_to_remove_from_row)

        if to_remove:
            remove_triples_in_batch(graph, to_remove)
            outcome.removed = len(to_remove)
        if to_add:
            add_triples_in_batch(graph, to_add)
            outcome.added = len(to_add)
        return outcome
