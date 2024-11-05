from pathlib import Path
from typing import Any, Literal, overload

from cognite.client import CogniteClient

from cognite.neat._graph import loaders
from cognite.neat._rules import exporters
from cognite.neat._session._wizard import space_wizard

from ._state import SessionState
from .exceptions import intercept_session_exceptions


@intercept_session_exceptions
class ToAPI:
    def __init__(self, state: SessionState, client: CogniteClient | None, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.cdf = CDFToAPI(state, client, verbose)

    def excel(
        self,
        io: Any,
    ) -> None:
        exporter = exporters.ExcelExporter()
        exporter.export_to_file(self._state.last_verified_rule, Path(io))
        return None

    @overload
    def yaml(self, io: None) -> str: ...

    @overload
    def yaml(self, io: Any) -> None: ...

    def yaml(self, io: Any | None = None) -> str | None:
        exporter = exporters.YAMLExporter()
        if io is None:
            return exporter.export(self._state.last_verified_rule)

        exporter.export_to_file(self._state.last_verified_rule, Path(io))
        return None


@intercept_session_exceptions
class CDFToAPI:
    def __init__(self, state: SessionState, client: CogniteClient | None, verbose: bool) -> None:
        self._client = client
        self._state = state
        self._verbose = verbose

    def instances(self, space: str | None = None):
        if not self._state.last_verified_dms_rules:
            raise ValueError("No verified DMS data model available")

        loader = loaders.DMSLoader.from_rules(
            self._state.last_verified_dms_rules, self._state.store, space_wizard(space=space)
        )

        if not self._client:
            raise ValueError("No client provided!")

        return loader.load_into_cdf(self._client)

    def data_model(self, existing_handling: Literal["fail", "skip", "update", "force"] = "skip"):
        """Export the verified DMS data model to CDF.

        Args:
            existing_handling: How to handle if component of data model exists. Defaults to "skip".

        """
        if not self._state.last_verified_dms_rules:
            raise ValueError("No verified DMS data model available")

        exporter = exporters.DMSExporter(existing_handling=existing_handling)

        if not self._client:
            raise ValueError("No client provided!")

        return exporter.export_to_cdf(self._state.last_verified_dms_rules, self._client)
