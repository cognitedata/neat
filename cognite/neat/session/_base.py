from typing import Literal

from cognite.client import CogniteClient

from cognite.neat.issues import IssueList

from ._read import ReadAPI
from ._state import SessionState
from ._to import ToAPI


class NeatSession:
    def __init__(
        self,
        client: CogniteClient | None = None,
        storage: Literal["memory", "oxigraph"] = "oxigraph",
        verbose: bool = True,
    ) -> None:
        self._client = client
        self._verbose = verbose
        self._state = SessionState(store_type=storage)
        self.read = ReadAPI(self._state, client, verbose)
        self.to = ToAPI(self._state, client, verbose)

    def verify(self) -> IssueList:
        raise NotImplementedError()

    def convert(self, target: Literal["dms"]) -> None:
        raise NotImplementedError()
