from typing import Literal

from cognite.client import CogniteClient

from ._read import ReadAPI
from ._to import ToAPI


class NeatSession:
    def __init__(
        self,
        client: CogniteClient | None,
        storage: Literal["memory", "oxigraph", "graphdb"] = "oxigraph",
        verbose: bool = True,
    ) -> None:
        self._client = client
        self._storage = storage
        self._verbose = verbose
        self.read = ReadAPI(client)
        self.to = ToAPI(client)
