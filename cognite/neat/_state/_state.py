from abc import ABC, abstractmethod

from ._types import Action


class State(ABC):
    @property
    def display_name(self) -> str:
        return type(self).__name__.removesuffix("State")

    @abstractmethod
    def is_valid_transition(self, action: Action) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def next_state(self, action: Action) -> "State":
        raise NotImplementedError()


class EmptyState(State):
    def is_valid_transition(self, action: Action) -> bool:
        raise NotImplementedError()

    def next_state(self, action: Action) -> "State":
        raise NotImplementedError()
