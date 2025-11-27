import json
from typing import Literal

from cognite.client import ClientConfig, CogniteClient

from cognite.neat import _version
from cognite.neat._client import NeatClient
from cognite.neat._config import internal_profiles
from cognite.neat._state_machine import EmptyState, PhysicalState
from cognite.neat._store import NeatStore
from cognite.neat._utils.http_client import ParametersRequest, SuccessResponse

from ._issues import Issues
from ._opt import Opt
from ._physical import PhysicalDataModel
from ._result import Result


class NeatSession:
    """A session is an interface for neat operations."""

    def __init__(
        self,
        client: CogniteClient | ClientConfig,
        config: Literal["legacy-additive", "legacy-rebuild", "deep-additive", "deep-rebuild"] | None = None,
    ) -> None:
        """Initialize a Neat session.

        Args:
            client (CogniteClient | ClientConfig): The Cognite client or client configuration to use for the session.
            config (Literal["legacy-additive", "legacy-rebuild", "deep-additive", "deep-rebuild"] | None):
                The configuration profile to use for the session.
                If None, the default profile "legacy-additive" is used. Meaning that Neat will perform additive modeling
                and apply only validations that were part of the legacy Neat version."""

        # Load configuration
        if config and config not in internal_profiles():
            raise ValueError(f"Profile '{config}' not found among internal profiles.")

        self._config = internal_profiles()[config or "legacy-additive"]

        # Use configuration for physical data model
        self._store = NeatStore()
        self._client = NeatClient(client)
        self.physical_data_model = PhysicalDataModel(self._store, self._client, self._config)
        self.issues = Issues(self._store)
        self.result = Result(self._store)
        self.opt = Opt(self._store)

        if self.opt._collector.can_collect:
            self.opt._collector.collect("initSession", {"mode": self._config.modeling.mode})

        self._welcome_message()

    def _welcome_message(self) -> None:
        cdf_project = self._client.config.project
        message = f"Neat session started for CDF project: '{cdf_project}'"
        responses = self._client.http_client.request(
            ParametersRequest(endpoint_url=self._client.config.create_api_url(""), method="GET")
        )
        if len(responses) == 1 and isinstance(response := responses[0], SuccessResponse):
            organization = ""
            try:
                organization = json.loads(response.body)["organization"]
            except (KeyError, ValueError):
                ...
            if organization:
                message += f" (Organization: '{organization}')"

        print(message)
        print(self._config)

    @property
    def version(self) -> str:
        """Get the current version of neat."""
        return _version.__version__

    def _repr_html_(self) -> str:
        if isinstance(self._store.state, EmptyState):
            return (
                "<strong>Empty session</strong>. Get started by reading for example physical data model"
                " <em>.physical_data_model.read</em>"
            )

        if isinstance(self._store.state, PhysicalState):
            return self.physical_data_model._repr_html_()

        raise RuntimeError("Unknown session state, contact support.")
