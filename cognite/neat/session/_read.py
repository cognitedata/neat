from pathlib import Path
from typing import Any

from cognite.client import CogniteClient

from cognite.neat.rules._shared import ReadRules
from cognite.neat.rules.importers import ExcelImporter

from ._state import SessionState


class ReadAPI:
    def __init__(self, state: SessionState, client: CogniteClient | None, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.cdf = CDFReadAPI(state, client)

    def excel(
        self,
        io: Any,
    ) -> None:
        if isinstance(io, str):
            filepath = Path(io)
        elif isinstance(io, Path):
            filepath = io
        else:
            raise ValueError(f"Expected str or Path, got {type(io)}")
        input_rules: ReadRules = ExcelImporter(filepath).to_rules()
        self._state.input_rules.append(input_rules)
        if self._verbose:
            print(f"Excel file {filepath} read successfully")


class CDFReadAPI:
    def __init__(self, state: SessionState, client: CogniteClient | None) -> None:
        self._state = state
        self._client = client
