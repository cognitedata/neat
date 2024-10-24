from pathlib import Path
from typing import Any, overload

from cognite.client import CogniteClient

from cognite.neat._rules.exporters import YAMLExporter
from cognite.neat._rules.exporters._rules2dms import DMSExporter

from ._state import SessionState


class ToAPI:
    def __init__(self, state: SessionState, client: CogniteClient | None, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.cdf = CDFToAPI(state, client, verbose)

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

    def __init__(
        self, state: SessionState, client: CogniteClient | None, verbose: bool
    ) -> None:
        self._client = client
        self._state = state
        self._verbose = verbose

    def instances(self, space: str | None = None):
        if not self._state.verifies_dms_rules:
            raise ValueError("No verified DMS data model available")

        space = space or self._state.verifies_dms_rules.metadata.space
        loader = loaders.DMSLoader.from_rules(
            self._state.verifies_dms_rules, self._state.store, space
        )

        if self._client:
            return loader.load_into_cdf(self._client)
        else:
            return loader.write_to_file(Path("./instance.yaml"))

    def data_model(self):
        if not self._state.verifies_dms_rules:
            raise ValueError("No verified DMS data model available")

        exporter = DMSExporter()

        if not self._client:
            return exporter.export_to_file(
                self._state.verifies_dms_rules, Path("./data_model.zip")
            )
        else:
            return exporter.export_to_cdf(self._state.verifies_dms_rules, self._client)
