from ._state import SessionState
from .exceptions import session_class_wrapper


@session_class_wrapper
class DropAPI:
    def __init__(self, state: SessionState):
        self._state = state

    def instances(self, type: str | list[str]) -> None:
        raise NotImplementedError
