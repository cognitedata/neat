from ._state_machine import EmptyState, ForbiddenState, State


class NeatSession:
    """A session is an interface for neat operations. It works as
    a manager for handling user interactions and orchestrating
    the state machine for data model and instance operations.
    """

    def __init__(self) -> None:
        self.state: State = EmptyState()

    def _execute_event(self, event: str) -> bool:
        """Place holder function for executing events and transitioning states.
        It will be modified to include actual logic as we progress with v1 of neat.

        """
        print(f"\n--- Executing event: '{event}' from {self.state} ---")

        old_state = self.state
        new_state = self.state.on_event(event)

        # Handle ForbiddenState
        if isinstance(new_state, ForbiddenState):
            print(f"❌ Event '{event}' is FORBIDDEN from {old_state}")
            # Return to previous state (as per your table logic)
            self.state = new_state.on_event("undo")
            print(f"↩️  Returned to: {self.state}")
            return False
        else:
            self.state = new_state
            print(f"✅ Transition successful: {old_state} → {self.state}")
            return True
