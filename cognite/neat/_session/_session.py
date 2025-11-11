from cognite.client import ClientConfig, CogniteClient

from cognite.neat._client import NeatClient
from cognite.neat._store import NeatStore
from cognite.neat._utils.useful_types import ModusOperandi

from ._issues import Issues
from ._opt import Opt
from ._physical import PhysicalDataModel
from ._result import Result


class NeatSession:
    """A session is an interface for neat operations. It works as
    a manager for handling user interactions and orchestrating
    the state machine for data model and instance operations.
    """

    def __init__(self, client: CogniteClient | ClientConfig, mode: ModusOperandi = "additive") -> None:
        self._store = NeatStore()
        self._client = NeatClient(client)
        self.physical_data_model = PhysicalDataModel(self._store, self._client)
        self.issues = Issues(self._store)
        self.result = Result(self._store)
        self.opt = Opt(self._store)

        if self.opt._collector.can_collect:
            self.opt._collector.collect("initSession", {"mode": mode})
