from cognite.client import data_modeling as dm

from cognite.neat._rules.transformers import SetIDDMSModel

from ._state import SessionState
from .exceptions import intercept_session_exceptions


@intercept_session_exceptions
class SetAPI:
    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

    def data_model_id(self, new_model_id: dm.DataModelId | tuple[str, str, str]) -> None:
        """Sets the data model ID of the latest verified data model."""
        if dms := self._state.last_verified_dms_rules:
            output = SetIDDMSModel(new_model_id).transform(dms)
            self._state.verified_rules.append(output.rules)
            if self._verbose:
                print(f"Data model ID set to {new_model_id}")
        else:
            print("No verified DMS data model available")
