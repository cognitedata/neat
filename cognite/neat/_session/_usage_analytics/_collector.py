import os
import platform
import threading
import uuid
from contextlib import suppress
from typing import Any, Literal

from mixpanel import Consumer, Mixpanel  # type: ignore[import-untyped]

from cognite.neat._session._usage_analytics._constants import IN_NOTEBOOK, IN_PYODIDE
from cognite.neat._session._usage_analytics._storage import ManualReadResult, ReadResult, get_storage

_NEAT_MIXPANEL_TOKEN: str = "bd630ad149d19999df3989c3a3750c4f"


class Collector:
    """Collects usage data and sends it to Mixpanel."""

    _instance: "Collector | None" = None
    _initialized: bool = False

    def __new__(cls, *args: Any, **kwargs: Any) -> "Collector":
        # Implementing Singleton pattern
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, skip_tracking: bool = False) -> None:
        if self._initialized:
            return
        self.mp = Mixpanel(_NEAT_MIXPANEL_TOKEN, consumer=Consumer(api_host="api-eu.mixpanel.com"))
        self._storage = get_storage()
        self._opt_status_key = "neat-opt-status"
        self._distinct_id_key = "neat-distinct-id"
        self.skip_tracking = skip_tracking
        self._initialized = True
        # We trigger these reads immediately to have them ready when needed.
        # This is necessary in a Pyodide environment were the read will not be available
        self._opt_status_read: ReadResult | None = self._storage.read(self._opt_status_key)
        self._distinct_id_read: ReadResult | None = self._storage.read(self._distinct_id_key)

    @property
    def _opt_status(self) -> str:
        if self._opt_status_read is None:
            self._opt_status_read = self._storage.read(self._opt_status_key)
        if self._opt_status_read.is_ready:
            return self._opt_status_read.get_data()
        return ""  # We do not have an opt status yet.

    @property
    def _distinct_id(self) -> str | None:
        if self._distinct_id_read is None:
            self._distinct_id_read = self._storage.read(self._distinct_id_key)
        if self._distinct_id_read.is_ready:
            return self._distinct_id_read.get_data()
        return None

    def bust_opt_status(self) -> None:
        self._storage.delete(self._opt_status_key)
        self._opt_status_read = None

    @property
    def is_opted_out(self) -> bool:
        return self._opt_status == "opted-out"

    @property
    def is_opted_in(self) -> bool:
        return self._opt_status == "opted-in"

    def enable(self) -> None:
        self._storage.write(self._opt_status_key, "opted-in")
        # Override cached property
        self._opt_status_read = ManualReadResult("opted-in")

    def disable(self) -> None:
        self._storage.write(self._opt_status_key, "opted-out")
        # Override cached property
        self._opt_status_read = ManualReadResult("opted-out")

    def get_distinct_id(self) -> str:
        existing_id = self._distinct_id
        if existing_id:
            return existing_id

        distinct_id = f"{platform.system()}-{platform.python_version()}-{uuid.uuid4()!s}"
        self._storage.write(self._distinct_id_key, distinct_id)
        with suppress(ConnectionError):
            self.mp.people_set(
                distinct_id,
                {
                    "$os": platform.system(),
                    "$python_version": platform.python_version(),
                    "$distinct_id": distinct_id,
                    "environment": self._get_environment(),
                },
            )
        self._distinct_id_read = ManualReadResult(distinct_id)
        return distinct_id

    @staticmethod
    def _get_environment() -> Literal["pyodide", "notebook", "python"]:
        """Get the current environment the user is running in."""
        if IN_PYODIDE:
            return "pyodide"
        if IN_NOTEBOOK:
            return "notebook"
        return "python"

    @property
    def can_collect(self) -> bool:
        """Check if tracking is possible."""
        return not self.skip_tracking and self.is_opted_in and "PYTEST_CURRENT_TEST" not in os.environ

    def collect(
        self, event_name: Literal["action", "initSession", "deployment"], event_properties: dict[str, Any]
    ) -> None:
        distinct_id = self.get_distinct_id()

        def track() -> None:
            # If we are unable to connect to Mixpanel, we don't want to crash the program
            with suppress(ConnectionError):
                self.mp.track(distinct_id, event_name, event_properties)

        if IN_PYODIDE:
            # We cannot spawn threads in Pyodide
            track()
            return None

        thread = threading.Thread(target=track, daemon=True)
        thread.start()
        return None
