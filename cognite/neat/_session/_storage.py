"""Storage abstraction for persisting data in both local filesystem and pyodide environments."""

from pathlib import Path
from typing import Protocol

from cognite.neat.v0.core._constants import IN_PYODIDE


class Storage(Protocol):
    """Protocol for storage implementations."""

    def read(self, key: str) -> str:
        """Read a value from storage."""
        ...

    def write(self, key: str, value: str) -> None:
        """Write a value to storage."""
        ...

    def delete(self, key: str) -> None:
        """Delete a value from storage."""
        ...


class FileSystemStorage:
    """Storage implementation using the filesystem."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def _get_path(self, key: str) -> Path:
        return self._base_dir / f"{key}.bin"

    def read(self, key: str) -> str:
        path = self._get_path(key)
        if path.exists():
            return path.read_text()
        return ""

    def write(self, key: str, value: str) -> None:
        path = self._get_path(key)
        path.write_text(value)

    def delete(self, key: str) -> None:
        path = self._get_path(key)
        path.unlink(missing_ok=True)


class LocalStorageAdapter:
    """Storage implementation using browser localStorage (for pyodide)."""

    def read(self, key: str) -> str:
        try:
            from js import localStorage  # type: ignore[import-not-found]

            value = localStorage.getItem(key)
            return value if value is not None else ""
        except Exception:
            return ""

    def write(self, key: str, value: str) -> None:
        try:
            from js import localStorage  # type: ignore[import-not-found]

            localStorage.setItem(key, value)
        except Exception:
            pass

    def delete(self, key: str) -> None:
        try:
            from js import localStorage  # type: ignore[import-not-found]

            localStorage.removeItem(key)
        except Exception:
            pass


def get_storage(base_dir: Path | None = None) -> Storage:
    """Get the appropriate storage implementation for the current environment."""
    if IN_PYODIDE:
        return LocalStorageAdapter()
    else:
        if base_dir is None:
            import tempfile

            base_dir = Path(tempfile.gettempdir()).resolve()
        return FileSystemStorage(base_dir)
