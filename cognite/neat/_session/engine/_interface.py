from typing import Any, Protocol


class NeatEngine(Protocol):
    interface_version: str = "0.1.0"

    def read(self, source_file: Any) -> str: ...
