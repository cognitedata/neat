"""Storage abstraction for persisting data in both local filesystem and pyodide environments."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    try:
        import asyncio

        from pyodide.webloop import PyodideTask  # type: ignore[import-not-found]
    except ImportError:
        pass

from cognite.neat._session._usage_analytics._constants import IN_PYODIDE


@dataclass
class ReadResult(ABC):
    @property
    @abstractmethod
    def is_ready(self) -> bool: ...

    @abstractmethod
    def get_data(self) -> str: ...


@dataclass
class ManualReadResult(ReadResult):
    data: str

    @property
    def is_ready(self) -> bool:
        return True

    def get_data(self) -> str:
        return self.data


class Storage(Protocol):
    """Protocol for storage implementations."""

    def read(self, key: str) -> ReadResult:
        """Read a value from storage."""
        ...

    def write(self, key: str, value: str) -> None:
        """Write a value to storage."""
        ...

    def delete(self, key: str) -> None:
        """Delete a value from storage."""
        ...


@dataclass
class FileReadResult(ReadResult):
    data: str

    @property
    def is_ready(self) -> bool:
        return True

    def get_data(self) -> str:
        return self.data


class FileSystemStorage:
    """Storage implementation using the filesystem."""

    ENCODING = "utf-8"

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def _get_path(self, key: str) -> Path:
        return self._base_dir / f"{key}.bin"

    def read(self, key: str) -> ReadResult:
        path = self._get_path(key)
        if path.exists():
            return FileReadResult(path.read_text(encoding=self.ENCODING))
        return FileReadResult("")

    def write(self, key: str, value: str) -> None:
        path = self._get_path(key)
        path.write_text(value, encoding=self.ENCODING)

    def delete(self, key: str) -> None:
        path = self._get_path(key)
        path.unlink(missing_ok=True)


@dataclass
class PyodideResult(ReadResult):
    task: "PyodideTask"

    @property
    def is_ready(self) -> bool:
        return self.task.done()

    def get_data(self) -> str:
        return self.task.result()


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

    def _execute_db_operation(self, operation: str, key: str, value: str | None = None) -> "PyodideTask":
        """Executes a database operation by creating and calling a JS function."""

        async def db_operation() -> str:
            import js  # type: ignore[import-not-found]
            from pyodide.code import run_js  # type: ignore[import-not-found]
            from pyodide.ffi import to_js  # type: ignore[import-not-found]

            # Convert Python values to JS
            js_key = to_js(key)
            js_value = to_js(value if value is not None else "")

            # Store values in js namespace temporarily to pass them safely
            js._idb_key = js_key
            js._idb_value = js_value

            try:
                # Create and execute the function directly in JavaScript context using run_js
                js_code = f"""
                (async () => {{
                    const dbName = "{self._db_name}";
                    const dbVersion = {self._db_version};
                    const storeName = "{self._store_name}";
                    const operation = "{operation}";

                    return new Promise((resolve, reject) => {{
                        const request = indexedDB.open(dbName, dbVersion);

                        request.onerror = (event) => reject(event.target.error);

                        request.onupgradeneeded = (event) => {{
                            const db = event.target.result;
                            if (!db.objectStoreNames.contains(storeName)) {{
                                db.createObjectStore(storeName);
                            }}
                        }};

                        request.onsuccess = (event) => {{
                            const db = event.target.result;
                            const mode = (operation === "read") ? "readonly" : "readwrite";
                            try {{
                                const transaction = db.transaction([storeName], mode);
                                const store = transaction.objectStore(storeName);

                                let storeRequest;
                                if (operation === "read") {{
                                    storeRequest = store.get(_idb_key);
                                }} else if (operation === "write") {{
                                    storeRequest = store.put(_idb_value, _idb_key);
                                }} else if (operation === "delete") {{
                                    storeRequest = store.delete(_idb_key);
                                }} else {{
                                    db.close();
                                    return reject(new Error(`Unknown operation: ${{operation}}`));
                                }}

                                storeRequest.onsuccess = () => resolve(storeRequest.result ?? "");
                                storeRequest.onerror = (event) => reject(event.target.error);

                                transaction.oncomplete = () => db.close();
                                transaction.onerror = (event) => reject(event.target.error);

                            }} catch (error) {{
                                db.close();
                                reject(error);
                            }}
                        }};
                    }});
                }})()
                """

                # Use run_js which properly returns an awaitable promise
                result = await run_js(js_code)
                return str(result) if result is not None else ""
            finally:
                # Clean up js namespace
                try:
                    del js._idb_key
                    del js._idb_value
                except Exception:
                    pass

        try:
            return self._loop.run_until_complete(db_operation())
        except Exception:
            return ""

    def read(self, key: str) -> ReadResult:
        return PyodideResult(self._execute_db_operation("read", key))

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
