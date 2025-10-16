from cognite.neat import _state_machine as states


class TestStateMachine:
    def test_empty_state_to_forbidden(self) -> None:
        initial_state = states.EmptyState()
        next_state = initial_state.transition("some_event")
        assert isinstance(next_state, states.ForbiddenState)

    def test_recovery_from_forbidden(self) -> None:
        initial_state = states.EmptyState()
        next_state = initial_state.transition("some_event")
        assert isinstance(next_state.transition(states.Undo()), states.EmptyState)
