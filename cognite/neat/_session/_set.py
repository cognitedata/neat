from cognite.client import data_modeling as dm

from cognite.neat._constants import COGNITE_MODELS
from cognite.neat._issues import IssueList
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.transformers import SetIDDMSModel

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class SetAPI:
    """Used to change the name of the data model from a data model id defined by neat to a user specified name."""

    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

    def data_model_id(self, new_model_id: dm.DataModelId | tuple[str, str, str]) -> IssueList:
        """Sets the data model ID of the latest verified data model. Set the data model id as a tuple of strings
        following the template (<data_model_space>, <data_model_name>, <data_model_version>).

        Example:
            Set a new data model id:
            ```python
            neat.set.data_model_id(("my_data_model_space", "My_Data_Model", "v1"))
            ```
        """
        rules = self._state.rule_store.get_last_successful_entity().result
        if isinstance(rules, DMSRules):
            if rules.metadata.as_data_model_id() in COGNITE_MODELS:
                raise NeatSessionError(
                    "Cannot change the data model ID of a Cognite Data Model in NeatSession"
                    " due to temporarily issue with the reverse direct relation interpretation"
                )
        return self._state.rule_transform(SetIDDMSModel(new_model_id))
