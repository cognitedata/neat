from cognite.neat.v0.core._constants import NAMED_GRAPH_NAMESPACE

from ._state import SessionState


class DiffAPI:
    """Compare RDF graphs (private API)."""

    def __init__(self, state: SessionState) -> None:
        self._state = state

    def instances(self, old_named_graph: str, new_named_graph: str) -> None:
        """
        Compare two named graphs and store diff results.

        Results stored in DIFF_ADD and DIFF_DELETE named graphs.

        Args:
            old_named_graph: Name of the old graph (e.g., "OLD")
            new_named_graph: Name of the new graph (e.g., "NEW")
        """
        old_uri = NAMED_GRAPH_NAMESPACE[old_named_graph]
        new_uri = NAMED_GRAPH_NAMESPACE[new_named_graph]

        self._state.instances.store.diff(old_uri, new_uri)
