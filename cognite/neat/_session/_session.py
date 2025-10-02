from cognite.neat._utils.http_client._client import HTTPClient

from ._state_machine import EmptyState, ForbiddenState, State


class NeatSession:
    def __init__(self, client: HTTPClient | None = None):
        self.state: State = EmptyState(client=client)

    def execute_event(self, event: str) -> bool:
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
            self.state = new_state.previous_state
            print(f"↩️  Returned to: {self.state}")
            return False
        else:
            self.state = new_state
            print(f"✅ Transition successful: {old_state} → {self.state}")
            return True
