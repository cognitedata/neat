from rdflib import URIRef

from ._state import SessionState
from .exceptions import session_class_wrapper

try:
    from rich import print
except ImportError:
    ...


@session_class_wrapper
class DropAPI:
    """
    Drop instances from the session. Check out `.instances()` for performing the operation.
    """

    def __init__(self, state: SessionState):
        self._state = state

    def instances(self, type: str | list[str]) -> None:
        """Drop instances from the session.

        Args:
            type: The type of instances to drop.

        Example:
            ```python
            node_type_to_drop = "Pump"
            neat.drop.instances(node_type_to_drop)
            ```
        """
        type_list = type if isinstance(type, list) else [type]
        uri_type_type = dict((v, k) for k, v in self._state.instances.store.queries.types.items())
        selected_uri_by_type: dict[URIRef, str] = {}
        for type_item in type_list:
            if type_item not in uri_type_type:
                print(f"Type {type_item} not found.")
            selected_uri_by_type[uri_type_type[type_item]] = type_item

        result = self._state.instances.store.queries.drop_types(list(selected_uri_by_type.keys()))

        for type_uri, count in result.items():
            print(f"Dropped {count} instances of type {selected_uri_by_type[type_uri]}")
        return None
