# /Users/nikola/repos/neat/cognite/neat/_session/_cdf.py
import uuid

from cognite.neat._client import NeatClient
from cognite.neat._config import NeatConfig
from cognite.neat._store._store import NeatStore

from ._html._render import render


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
                "node_types": len(self._store.cdf_snapshot.node_types),
            },
        )
