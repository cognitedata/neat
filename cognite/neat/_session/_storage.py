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
    """Storage implementation using browser IndexedDB (for pyodide)."""

    def __init__(self) -> None:
        self._db_name = "neat-storage"
        self._store_name = "keyval"
        self._db_version = 1

    def _execute_db_operation(self, operation: str, key: str, value: str | None = None) -> str:
        """Execute a database operation using IndexedDB."""
        try:
            import asyncio

            import js  # type: ignore[import-not-found]

            # Check if we have an event loop, if not create one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Define the async operation
            async def db_operation() -> str:
                # Create JavaScript promise that handles IndexedDB operations
                js_promise = js.Promise.new(
                    js.Function.new(
                        "resolve",
                        "reject",
                        f"""
                        const request = indexedDB.open('{self._db_name}', {self._db_version});

                        request.onerror = () => reject(request.error);

                        request.onupgradeneeded = (event) => {{
                            const db = event.target.result;
                            if (!db.objectStoreNames.contains('{self._store_name}')) {{
                                db.createObjectStore('{self._store_name}');
                            }}
                        }};

                        request.onsuccess = (event) => {{
                            const db = event.target.result;
                            const mode = {'"readwrite"' if operation in ("write", "delete") else '"readonly"'};
                            const transaction = db.transaction(['{self._store_name}'], mode);
                            const store = transaction.objectStore('{self._store_name}');

                            let storeRequest;
                            if ('{operation}' === 'read') {{
                                storeRequest = store.get('{key}');
                            }} else if ('{operation}' === 'write') {{
                                storeRequest = store.put('{value if value else ""}', '{key}');
                            }} else if ('{operation}' === 'delete') {{
                                storeRequest = store.delete('{key}');
                            }}

                            storeRequest.onsuccess = () => {{
                                db.close();
                                resolve(storeRequest.result || '');
                            }};

                            storeRequest.onerror = () => {{
                                db.close();
                                reject(storeRequest.error);
                            }};
                        }};
                        """,
                    )
                )

                # Convert JS promise to Python awaitable
                result = await js_promise
                return str(result) if result else ""

            # Run the async operation
            return loop.run_until_complete(db_operation())
        except Exception:
            return ""

    def read(self, key: str) -> str:
        return self._execute_db_operation("read", key)

    def write(self, key: str, value: str) -> None:
        self._execute_db_operation("write", key, value)

    def delete(self, key: str) -> None:
        self._execute_db_operation("delete", key)


def get_storage(base_dir: Path | None = None) -> Storage:
    """Get the appropriate storage implementation for the current environment."""
    if IN_PYODIDE:
        return LocalStorageAdapter()
    else:
        if base_dir is None:
            import tempfile

            base_dir = Path(tempfile.gettempdir()).resolve()
        return FileSystemStorage(base_dir)
