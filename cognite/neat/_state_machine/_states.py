from typing import Any

from cognite.neat._data_model.exporters import DMSExporter
from cognite.neat._data_model.importers import DMSImporter

from ._base import State


class Undo:
    """
    Event to trigger undoing the last action.
    """

    pass


class ForbiddenState(State):
    """
    State representing forbidden transitions - returns to previous state.
    """

    def __init__(self, previous_state: State):
        self.previous_state = previous_state
        print(f"Forbidden action attempted. Returning to previous state: {previous_state}")

    def transition(self, event: Any) -> State:
        # only "undo" to trigger going back to previous state
        if isinstance(event, Undo):
            return self.previous_state
        return self


class EmptyState(State):
    """
    The initial state with empty NEAT store.
    """

    def transition(self, event: Any) -> State:
        if isinstance(event, DMSImporter):
            return PhysicalState()
        return ForbiddenState(self)


class PhysicalState(State):
    """
    State with physical model loaded.
    """

    def transition(self, event: Any) -> State:
        if isinstance(event, DMSExporter):
            return PhysicalState()

        return ForbiddenState(self)
