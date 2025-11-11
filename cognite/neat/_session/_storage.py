"""Storage abstraction for persisting data in both local filesystem and pyodide environments."""

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from cognite.neat.v0.core._constants import IN_PYODIDE

if TYPE_CHECKING:
    import asyncio

    import js  # type: ignore[import-not-found]


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
    """
    Storage implementation using browser IndexedDB for pyodide environments.

    This adapter provides a synchronous interface to the asynchronous IndexedDB API
    by managing an asyncio event loop.
    """

    _db_name = "neat-storage"
    _store_name = "keyval"
    _db_version = 1

    def __init__(self) -> None:
        self._loop = self._get_or_create_event_loop()
        self._db_operation_func = self._create_js_function()

    @staticmethod
    def _get_or_create_event_loop() -> "asyncio.AbstractEventLoop":
        """Gets the current asyncio event loop or creates a new one."""
        import asyncio

        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    def _create_js_function(self) -> "js.Function":
        """Creates a reusable JavaScript function for all database operations."""
        import js  # type: ignore[import-not-found]

        # This JS code is defined once and parameterized to avoid injection.
        js_code = """
        (dbName, dbVersion, storeName, operation, key, value) => {
            return new Promise((resolve, reject) => {
                const request = indexedDB.open(dbName, dbVersion);

                request.onerror = (event) => reject(event.target.error);

                request.onupgradeneeded = (event) => {
                    const db = event.target.result;
                    if (!db.objectStoreNames.contains(storeName)) {
                        db.createObjectStore(storeName);
                    }
                };

                request.onsuccess = (event) => {
                    const db = event.target.result;
                    const mode = (operation === "read") ? "readonly" : "readwrite";
                    try {
                        const transaction = db.transaction([storeName], mode);
                        const store = transaction.objectStore(storeName);

                        let storeRequest;
                        if (operation === "read") {
                            storeRequest = store.get(key);
                        } else if (operation === "write") {
                            storeRequest = store.put(value, key);
                        } else if (operation === "delete") {
                            storeRequest = store.delete(key);
                        } else {
                            db.close();
                            return reject(new Error(`Unknown operation: ${operation}`));
                        }

                        storeRequest.onsuccess = () => resolve(storeRequest.result ?? "");
                        storeRequest.onerror = (event) => reject(event.target.error);

                        transaction.oncomplete = () => db.close();
                        transaction.onerror = (event) => reject(event.target.error);

                    } catch (error) {
                        db.close();
                        reject(error);
                    }
                };
            });
        }
        """
        return js.Function.new("dbName", "dbVersion", "storeName", "operation", "key", "value", js_code)

    def _execute_db_operation(self, operation: str, key: str, value: str | None = None) -> str:
        """Executes a database operation by calling the reusable JS function."""

        async def db_operation() -> str:
            js_promise = self._db_operation_func(
                self._db_name, self._db_version, self._store_name, operation, key, value
            )
            result = await js_promise
            return str(result) if result is not None else ""

        try:
            # Bridge the async JS call from our synchronous Python method.
            return self._loop.run_until_complete(db_operation())
        except Exception:
            # Fallback to empty string in case of any storage errors.
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
