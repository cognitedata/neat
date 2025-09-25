import dataclasses
import warnings
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import ClassVar, TypeAlias, cast

from rdflib import Graph
from rdflib.query import ResultRow

from cognite.neat.v0.core._issues.warnings import NeatValueWarning
from cognite.neat.v0.core._shared import Triple
from cognite.neat.v0.core._utils.collection_ import (
    iterate_progress_bar_if_above_config_threshold,
)
from cognite.neat.v0.core._utils.graph_transformations_report import (
    GraphTransformationResult,
)

To_Add_Triples: TypeAlias = set[Triple]
To_Remove_Triples: TypeAlias = set[Triple]


@dataclasses.dataclass
class RowTransformationOutput:
    remove_triples: To_Remove_Triples = dataclasses.field(default_factory=set)
    add_triples: To_Add_Triples = dataclasses.field(default_factory=set)
    instances_removed_count: int = 0
    instances_added_count: int = 0
    instances_modified_count: int = 0


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

    description: str
    _use_only_once: bool = False
    _need_changes: ClassVar[frozenset[str]] = frozenset()

    @abstractmethod
    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
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

        !!! note "Complex Queries"
            In majority of cases the query should be a simple SELECT query. However, in case
            when there is a need to have one or more sub iterators, one can overwrite the ._iterator() method
        """
        raise NotImplementedError()

    def _iterator(self, graph: Graph) -> Iterator:
        yield from graph.query(self._iterate_query())

    def _skip_count_query(self) -> str:
        """
        The query to use for extracting target triples from the graph and performing the transformation.
        Returns:
            A query string.
        """
        return ""

    def transform(self, graph: Graph) -> GraphTransformationResult:
        outcome = GraphTransformationResult(self.__class__.__name__)
        outcome.added = outcome.modified = outcome.removed = 0

        iteration_count_res = list(graph.query(self._count_query()))
        iteration_count = int(iteration_count_res[0][0])  # type: ignore [index, arg-type]

        outcome.affected_nodes_count = iteration_count

        if self._skip_count_query():
            skipped_count_res = list(graph.query(self._skip_count_query()))
            skipped_count = int(skipped_count_res[0][0])  # type: ignore [index, arg-type]
            if skipped_count > 0:
                warnings.warn(
                    NeatValueWarning(
                        f"Skipping {skipped_count} properties in transformation {self.__class__.__name__}"
                    ),
                    stacklevel=2,
                )
            outcome.skipped = skipped_count

        if iteration_count == 0:
            return outcome

        result_iterable = self._iterator(graph)
        result_iterable = iterate_progress_bar_if_above_config_threshold(
            result_iterable, iteration_count, self.description
        )

        for row in result_iterable:
            row = cast(ResultRow, row)
            row_output = self.operation(row)

            outcome.added += row_output.instances_added_count
            outcome.removed += row_output.instances_removed_count
            outcome.modified += row_output.instances_modified_count

            for triple in row_output.add_triples:
                graph.add(triple)
            for triple in row_output.remove_triples:
                graph.remove(triple)

        return outcome
