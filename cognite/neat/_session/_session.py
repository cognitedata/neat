from cognite.neat._store import NeatStore

from ._physical import PhysicalDataModel


class NeatSession:
    """A session is an interface for neat operations. It works as
    a manager for handling user interactions and orchestrating
    the state machine for data model and instance operations.
    """

    def __init__(self) -> None:
        self._store = NeatStore()
        self.physical_data_model = PhysicalDataModel(self._store)
