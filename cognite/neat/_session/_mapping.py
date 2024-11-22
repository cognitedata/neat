from cognite.neat._rules.models.mapping import create_classic_to_core_mapping
from cognite.neat._rules.transformers import RuleMapper

from ._state import SessionState
from .exceptions import session_class_wrapper


@session_class_wrapper
class MappingAPI:
    def __init__(self, state: SessionState):
        self._state = state

    def classic_to_core(self, org_name: str) -> None:
        """Map classic types to core types.

        Note this automatically creates an extended CogniteCore model.

        """
        _ = RuleMapper(create_classic_to_core_mapping(org_name))

        raise NotImplementedError("This method is not yet implemented.")
