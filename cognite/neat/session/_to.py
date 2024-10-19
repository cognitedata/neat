from typing import Any

from cognite.client import CogniteClient


class ToAPI:
    def __init__(self, client: CogniteClient | None = None) -> None:
        self.cdf = CDFToAPI(client)

    def excel(
        self,
        io: Any,
    ) -> None: ...

    def yaml(self, io: Any) -> None: ...


class CDFToAPI:
    def __init__(self, client: CogniteClient | None) -> None:
        self._client = client
