from datetime import datetime, timezone

from cognite.client import data_modeling as dm

from cognite.neat._rules.transformers import SetIDDMSModel
from cognite.neat._store._provenance import Change

from ._state import SessionState
from .exceptions import intercept_session_exceptions


@intercept_session_exceptions
class SetAPI:
    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

    def data_model_id(self, new_model_id: dm.DataModelId | tuple[str, str, str]) -> None:
        """Sets the data model ID of the latest verified data model."""
        if res := self._state.data_model.last_verified_dms_rules:
            source_id, rules = res

            start = datetime.now(timezone.utc)
            transformer = SetIDDMSModel(new_model_id)
            output = transformer.transform(rules)
            end = datetime.now(timezone.utc)

            # Provenance
            change = Change.from_rules_activity(
                output,
                transformer.agent,
                start,
                end,
                "Changed data model id",
                self._state.data_model.provenance.entity(source_id),
            )

            self._state.data_model.write(output, change)
            if self._verbose:
                print(f"Data model ID set to {new_model_id}")
        else:
            print("No verified DMS data model available")
