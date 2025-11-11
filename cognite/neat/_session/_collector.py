import os
import platform
import tempfile
import threading
import uuid
from contextlib import suppress
from functools import cached_property
from pathlib import Path
from typing import Any, Literal

from mixpanel import Consumer, Mixpanel  # type: ignore[import-untyped]

from cognite.neat.v0.core._constants import IN_NOTEBOOK, IN_PYODIDE

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
        tmp_dir = Path(tempfile.gettempdir()).resolve()
        self._opt_status_file = tmp_dir / "neat-opt-status.bin"
        self._distinct_id_file = tmp_dir / "neat-distinct-id.bin"
        self.skip_tracking = self.is_opted_out or skip_tracking
        self._initialized = True

    @cached_property
    def _opt_status(self) -> str:
        if self._opt_status_file.exists():
            return self._opt_status_file.read_text()
        return ""

    def bust_opt_status(self) -> None:
        self.__dict__.pop("_opt_status", None)
        self._opt_status_file.unlink(missing_ok=True)

    @property
    def is_opted_out(self) -> bool:
        return self._opt_status == "opted-out"

    @property
    def is_opted_in(self) -> bool:
        return self._opt_status == "opted-in"

    def enable(self) -> None:
        self._opt_status_file.write_text("opted-in")
        # Override cached property
        self.__dict__["_opt_status"] = "opted-in"

    def disable(self) -> None:
        self._opt_status_file.write_text("opted-out")
        # Override cached property
        self.__dict__["_opt_status"] = "opted-out"

    def get_distinct_id(self) -> str:
        if self._distinct_id_file.exists():
            return self._distinct_id_file.read_text()

        distinct_id = f"{platform.system()}-{platform.python_version()}-{uuid.uuid4()!s}"
        self._distinct_id_file.write_text(distinct_id)
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
        return distinct_id

    @staticmethod
    def _get_environment() -> Literal["pyodide", "notebook", "python"]:
        """Get the current environment the user is running in."""
        if IN_PYODIDE:
            return "pyodide"
        if IN_NOTEBOOK:
            return "notebook"
        return "python"

    def track_session_command(
        self,
        even_name: Literal["action"],
    ) -> None:
        raise NotImplementedError()

    def _track(self, event_name: str, event_properties: dict[str, Any]) -> bool:
        if self.skip_tracking or not self.is_opted_in or "PYTEST_CURRENT_TEST" in os.environ:
            return False

        distinct_id = self.get_distinct_id()

        def track() -> None:
            # If we are unable to connect to Mixpanel, we don't want to crash the program
            with suppress(ConnectionError):
                self.mp.track(distinct_id, event_name, event_properties)

        thread = threading.Thread(target=track, daemon=False)
        thread.start()
        return True
