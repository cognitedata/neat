from abc import ABC, abstractmethod


class State(ABC):
    def __init__(self) -> None:
        # this will be reference to the actual store in the session
        # used to store data models and instances, here only as a placeholder
        self._store = None

    @abstractmethod
    def on_event(self, event: str) -> "State":
        """
        Handle events that are delegated to this State.
        """
        raise NotImplementedError("on_event() must be implemented by the subclass.")

    def __repr__(self) -> str:
        """
        Leverages the __str__ method to describe the State.
        """
        return self.__str__()

    def __str__(self) -> str:
        """
        Returns the name of the State.
        """
        return self.__class__.__name__
