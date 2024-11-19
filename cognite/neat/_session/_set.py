from datetime import datetime, timezone

from cognite.client import data_modeling as dm

from cognite.neat._constants import COGNITE_MODELS
from cognite.neat._rules.transformers import SetIDDMSModel
from cognite.neat._store._provenance import Change

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class SetAPI:
    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

    def data_model_id(self, new_model_id: dm.DataModelId | tuple[str, str, str]) -> None:
        """Sets the data model ID of the latest verified data model."""
        if res := self._state.data_model.last_verified_dms_rules:
            source_id, rules = res

            if rules.metadata.as_data_model_id() in COGNITE_MODELS:
                raise NeatSessionError(
                    "Cannot change the data model ID of a Cognite Data Model in NeatSession"
                    " due to temporarily issue with the reverse direct relation interpretation"
                )

            start = datetime.now(timezone.utc)
            transformer = SetIDDMSModel(new_model_id)
            output = transformer.transform(rules)
            end = datetime.now(timezone.utc)

            # Provenance
            change = Change.from_rules_activity(
                output.rules,
                transformer.agent,
                start,
                end,
                "Changed data model id",
                self._state.data_model.provenance.source_entity(source_id)
                or self._state.data_model.provenance.target_entity(source_id),
            )

            self._state.data_model.write(output.rules, change)
            if self._verbose:
                print(f"Data model ID set to {new_model_id}")
        else:
            print("No verified DMS data model available")
