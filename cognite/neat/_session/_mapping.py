from ._state import SessionState
from .exceptions import session_class_wrapper


@session_class_wrapper
class MappingAPI:
    def __init__(self, state: SessionState):
        self._state = state

    def classic_to_core(self, org_name: str = "My") -> None:
        """Map classic types to core types.

        Note this automatically creates an extended CogniteCore model.

        Args:
            org_name: The name of your organization.

        """
        ...
