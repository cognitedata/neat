from pathlib import Path
from typing import Any, overload

from cognite.client import CogniteClient

from cognite.neat.rules.exporters import YAMLExporter

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

    @overload
    def yaml(self, io: None) -> str: ...

    @overload
    def yaml(self, io: Any) -> None: ...

    def yaml(self, io: Any | None = None) -> str | None:
        exporter = YAMLExporter()
        if io is None:
            return exporter.export(self._state.verified_rule)

        exporter.export_to_file(self._state.verified_rule, Path(io))
        return None


class CDFToAPI:
    def __init__(self, client: CogniteClient | None) -> None:
        self._client = client
