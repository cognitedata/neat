import os
import platform
import tempfile
import threading
import uuid
from contextlib import suppress
from functools import cached_property
from pathlib import Path
from typing import Any

from mixpanel import Consumer, Mixpanel  # type: ignore[import-untyped]

from cognite.neat._version import __version__
from cognite.neat.v0.core._constants import IN_NOTEBOOK, IN_PYODIDE

_NEAT_MIXPANEL_TOKEN: str = "bd630ad149d19999df3989c3a3750c4f"


class Collector:
    def __init__(self, skip_tracking: bool = False) -> None:
        self.mp = Mixpanel(_NEAT_MIXPANEL_TOKEN, consumer=Consumer(api_host="api-eu.mixpanel.com"))
        tmp_dir = Path(tempfile.gettempdir()).resolve()
        self._opt_status_file = tmp_dir / "neat-opt-status.bin"
        self._distinct_id_file = tmp_dir / "neat-distinct-id.bin"
        self.skip_tracking = self.opted_out or skip_tracking

    @cached_property
    def _opt_status(self) -> str:
        if self._opt_status_file.exists():
            return self._opt_status_file.read_text()
        return ""

    def _bust_opt_status(self) -> None:
        self.__dict__.pop("_opt_status", None)

    @property
    def opted_out(self) -> bool:
        return self._opt_status == "opted-out"

    @property
    def opted_in(self) -> bool:
        return self._opt_status == "opted-in"

    @staticmethod
    def _get_environment() -> str:
        if IN_PYODIDE:
            return "pyodide"
        if IN_NOTEBOOK:
            return "notebook"
        return "python"

    def track_session_command(self, command: str, *args: Any, **kwargs: Any) -> None:
        event_information = {
            "neatVersion": __version__,
            "$os": platform.system(),
            "pythonVersion": platform.python_version(),
            "environment": self._get_environment(),
        }

        if len(args) > 1:
            # The first argument is self.
            for i, arg in enumerate(args[1:]):
                event_information[f"arg{i}"] = self._serialize_value(arg)[:500]

        if kwargs:
            for key, value in kwargs.items():
                event_information[key] = self._serialize_value(value)[:500]

        with suppress(RuntimeError):
            # In case any thread issues, the tracking should not crash the program
            self._track(command, event_information)

    @staticmethod
    def _serialize_value(value: Any) -> str:
        if isinstance(value, (str | int | float | bool)):
            return str(value)
        if isinstance(value, list | tuple | dict):
            return str(value)
        if callable(value):
            return value.__name__
        return str(type(value))

    def _track(self, event_name: str, event_information: dict[str, Any]) -> bool:
        if self.skip_tracking or not self.opted_in or "PYTEST_CURRENT_TEST" in os.environ:
            return False

        distinct_id = self.get_distinct_id()

        def track() -> None:
            # If we are unable to connect to Mixpanel, we don't want to crash the program
            with suppress(ConnectionError):
                self.mp.track(
                    distinct_id,
                    event_name,
                    event_information,
                )

        thread = threading.Thread(
            target=track,
            daemon=False,
        )
        thread.start()
        return True

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
                },
            )
        return distinct_id

    def enable(self) -> None:
        self._opt_status_file.write_text("opted-in")
        self._bust_opt_status()

    def disable(self) -> None:
        self._opt_status_file.write_text("opted-out")
        self._bust_opt_status()


_COLLECTOR = Collector()
