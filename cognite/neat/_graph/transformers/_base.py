from abc import ABC, abstractmethod
from typing import ClassVar, Literal

from rdflib import Graph

from cognite.neat._issues import IssueList
from cognite.neat._utils.collection_ import iterate_progress_bar
from cognite.neat._utils.graph_transformations_report import GraphTransformationResult


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
    def operation(self) -> Literal["add", "remove"]:
        raise NotImplementedError()

    def _target_properties_count_query(self) -> str | None:  # noqa: B027
        """
        Overwrite to fetch all affected properties in the graph as a result of the transformation.
        Returns:
            A query string.
        """
        ...

    def _target_edges_count_query(self) -> str | None:  # noqa: B027
        """
        Overwrite to fetch all affected edges (objects) in the graph
        as a result of the transformation.
        Returns:
            A query string.
        """
        ...

    def _skip_query(self) -> str | None:  # noqa: B027
        """
        Overwrite to fetch all affected triples (subjects, objects and predicates) in
        the graph as a result of the transformation.
        Returns:
            A query string.
        """
        ...

    @abstractmethod
    def _iterate_query(self) -> str:
        """
        The query to use for extracting target triples from the graph and performing the transformation.
        Returns:
            A query string.
        """
        raise NotImplementedError()

    def transform(self, graph: Graph) -> GraphTransformationResult:
        added_entities = []
        removed_entities = []
        skipped_entities = []
        affected_nodes_count = 0
        issues: IssueList = IssueList([])

        if self._skip_query():
            skipped_entities = graph.query(self._skip_query())
            skipped_entities = [str(triple) for triple in skipped_entities]

        targets = list(graph.query(self._iterate_query()))

        if len(targets) == 0:
            issues.append("Transformation has no effect. Found 0 target triples in the graph.")

        if self._target_properties_count_query():
            affected_nodes_count += len(list(graph.query(self._target_properties_count_query())))
        if self._target_edges_count_query():
            affected_nodes_count += len(list(graph.query(self._target_edges_count_query())))

        use_iterate_bar = True if len(targets) > self._use_iterate_bar_threshold else False
        if use_iterate_bar:
            for triple in iterate_progress_bar(  # type: ignore[misc]
                targets,
                total=len(targets),
                description=self.description,
            ):
                mask = [None, None, None, None]
                for i, item in enumerate(triple):
                    mask[i] = item
                formatted_triple = tuple(mask)

                if self.operation() == "add":
                    graph.add(formatted_triple)
                    added_entities.append(str(triple))

                elif self.operation() == "remove":
                    graph.remove(formatted_triple)
                    removed_entities.append(str(triple))

        else:
            for triple in targets:
                mask = [None, None, None, None]
                for i, item in enumerate(triple):
                    mask[i] = item
                formatted_triple = tuple(mask)

                if self.operation() == "add":
                    graph.add(formatted_triple)
                    added_entities.append(str(triple))

                elif self.operation() == "remove":
                    graph.remove(formatted_triple)
                    removed_entities.append(str(triple))

        return GraphTransformationResult(
            name=self.__class__.__name__,
            affected_nodes_count=affected_nodes_count if affected_nodes_count else None,
            added=added_entities,
            removed=removed_entities,
            skipped=skipped_entities,
            issues=issues,
        )
