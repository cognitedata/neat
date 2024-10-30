import pandas as pd

from ._state import SessionState
from .exceptions import intercept_session_exceptions


@intercept_session_exceptions
class InspectAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    @property
    def properties(self) -> pd.DataFrame:
        """Returns the properties of the current data model."""
        return self._state.last_verified_rule.properties.to_pandas()
