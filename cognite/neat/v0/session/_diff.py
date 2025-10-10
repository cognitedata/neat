from typing import cast

from rdflib.query import ResultRow

from cognite.neat.v0.core._constants import NAMED_GRAPH_NAMESPACE

from ._state import SessionState


class DiffAPI:
    """Compare RDF graphs (private API)."""

    def __init__(self, state: SessionState) -> None:
        self._state = state

    def instances(self, current_named_graph: str, new_named_graph: str) -> None:
        """
        Compare two named graphs and store diff results.

        Results stored in DIFF_ADD and DIFF_DELETE named graphs.

        Args:
            current_named_graph: Name of the current graph (e.g., "CURRENT")
            new_named_graph: Name of the new graph (e.g., "NEW")
        """
        current_uri = NAMED_GRAPH_NAMESPACE[current_named_graph]
        new_uri = NAMED_GRAPH_NAMESPACE[new_named_graph]

        self._state.instances.store.diff(current_uri, new_uri)
        self._print_summary()

    def _print_summary(self) -> None:
        """Print diff summary with triple counts."""
        store = self._state.instances.store

        add_query = (
            f"SELECT (COUNT(*) as ?count) WHERE {{ GRAPH <{NAMED_GRAPH_NAMESPACE['DIFF_ADD']}> {{ ?s ?p ?o }} }}"
        )
        delete_query = (
            f"SELECT (COUNT(*) as ?count) WHERE {{ GRAPH <{NAMED_GRAPH_NAMESPACE['DIFF_DELETE']}> {{ ?s ?p ?o }} }}"
        )

        add_result = cast(ResultRow, next(iter(store.dataset.query(add_query))))
        delete_result = cast(ResultRow, next(iter(store.dataset.query(delete_query))))

        add_count = int(add_result[0])
        delete_count = int(delete_result[0])

        print("Diff complete:")
        print(f"  {add_count} triples to add (stored in DIFF_ADD)")
        print(f"  {delete_count} triples to delete (stored in DIFF_DELETE)")
