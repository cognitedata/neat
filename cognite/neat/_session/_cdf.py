import uuid

from cognite.neat._client import NeatClient
from cognite.neat._config import NeatConfig
from cognite.neat._data_model.rules.cdf._orchestrator import CDFRulesOrchestrator
from cognite.neat._session._wrappers import session_wrapper
from cognite.neat._store._store import NeatStore

from ._html._render import render


@session_wrapper
class CDF:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, store: NeatStore, client: NeatClient, config: NeatConfig) -> None:
        self._store = store
        self._client = client
        self._config = config

    def _repr_html_(self) -> str:
        """Generate HTML representation of CDF schema statistics."""
        unique_id = str(uuid.uuid4())[:8]

        return render(
            "statistics",
            {
                "unique_id": unique_id,
                "spaces_current": self._store.cdf_limits.spaces.count,
                "spaces_limit": self._store.cdf_limits.spaces.limit,
                "containers_current": self._store.cdf_limits.containers.count,
                "containers_limit": self._store.cdf_limits.containers.limit,
                "views_current": self._store.cdf_limits.views.count,
                "views_limit": self._store.cdf_limits.views.limit,
                "data_models_current": self._store.cdf_limits.data_models.count,
                "data_models_limit": self._store.cdf_limits.data_models.limit,
            },
        )

    def analyze(self) -> None:
        """Analyze the entity of CDF data models."""

        on_success = CDFRulesOrchestrator(
            limits=self._store.cdf_limits,
            space_statistics=self._store.cdf_space_statistics,
            can_run_validator=self._config.validation.can_run_validator,
            enable_alpha_validators=self._config.alpha.enable_experimental_validators,
        )

        return self._store.cdf_analyze(on_success)
