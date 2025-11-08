from cognite.client import ClientConfig, CogniteClient

from cognite.neat._client import NeatClient
from cognite.neat._store import NeatStore

from ._issues import Issues
from ._physical import PhysicalDataModel
from ._result import Result


class NeatSession:
    """A session is an interface for neat operations. It works as
    a manager for handling user interactions and orchestrating
    the state machine for data model and instance operations.
    """

    def __init__(self, client: CogniteClient | ClientConfig) -> None:
        self._store = NeatStore()
        self._client = NeatClient(client)
        self.physical_data_model = PhysicalDataModel(self._store, self._client)
        self.issues = Issues(self._store)
        self.result = Result(self._store)
