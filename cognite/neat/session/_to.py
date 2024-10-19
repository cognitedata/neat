from typing import Any

from cognite.client import CogniteClient

from ._state import SessionState


class ToAPI:
    def __init__(self, state: SessionState, client: CogniteClient | None, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.cdf = CDFToAPI(client)

    def excel(
        self,
        io: Any,
    ) -> None: ...

    def yaml(self, io: Any | None = None) -> None: ...


class CDFToAPI:
    def __init__(self, client: CogniteClient | None) -> None:
        self._client = client
