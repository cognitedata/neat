import pandas as pd

from ._state import SessionState
from .exceptions import session_class_wrapper


@session_class_wrapper
class ExploreAPI:
    """
    Explore the instances in the session.
    """

    def __init__(self, state: SessionState):
        self._state = state

    def types(self) -> pd.DataFrame:
        """List all the types of instances in the session."""
        return pd.DataFrame(self._state.instances.store.queries.types_with_instance_and_property_count())

    def properties(self) -> pd.DataFrame:
        """List all the properties of a type of instances in the session."""
        raise NotImplementedError()
