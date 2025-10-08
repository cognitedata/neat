from typing import Any

from rdflib import URIRef

from ._state import SessionState


class DiffAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def instances(self, old_named_graph: URIRef, new_named_graph: URIRef, *args: tuple[Any, ...]) -> None:
        self._state.instances.store.diff(old_named_graph, new_named_graph, *args)
