from ._state import SessionState
from .exceptions import session_class_wrapper
from cognite.neat._rules.models.mapping import create_classic_to_core_mapping
from cognite.neat._rules.transformers import RuleMapper


@session_class_wrapper
class MappingAPI:
    def __init__(self, state: SessionState):
        self._state = state

    def classic_to_core(self) -> None:
        """Map classic types to core types.

        Note this automatically creates an extended CogniteCore model.

        """
        transformer = RuleMapper(create_classic_to_core_mapping())

        self._state.data_model.write(transformer.transform(self._state.data_model.last_verified_dms_rules))
