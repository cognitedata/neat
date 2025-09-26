import tempfile
from abc import ABC, abstractmethod
from collections.abc import Iterable
from io import StringIO
from pathlib import Path
from typing import IO, Any, TextIO
from urllib.parse import urlparse

import requests

from cognite.neat.v0.core._issues.errors import NeatTypeError, NeatValueError


class NeatReader(ABC):
    @classmethod
    def create(cls, io: Any) -> "NeatReader":
        if isinstance(io, str):
            url = urlparse(io)
            if url.scheme == "https" and url.netloc.endswith("github.com"):
                return GitHubReader(io)
            elif url.scheme == "https":
                return HttpFileReader(io, url.path)

        if isinstance(io, str | Path):
            return PathReader(Path(io))
        raise NeatTypeError(f"Unsupported type: {type(io)}")

    @property
    def name(self) -> str:
        return str(self)

    @abstractmethod
    def read_text(self) -> str:
        """Read the buffer as a string"""
        raise NotImplementedError()

    @abstractmethod
    def read_bytes(self) -> bytes:
        """Read the buffer as bytes"""
        raise NotImplementedError()

    @abstractmethod
    def size(self) -> int:
        """Size of the buffer in bytes"""
        raise NotImplementedError()

    @abstractmethod
    def iterate(self, chunk_size: int) -> Iterable[str]:
        """Iterate over the buffer in chunks

        Args:
            chunk_size: Size of each chunk in bytes
        """
        raise NotImplementedError()

    @abstractmethod
    def __enter__(self) -> IO:
        raise NotImplementedError()

    @abstractmethod
    def __str__(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    def exists(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def materialize_path(self) -> Path:
        raise NotImplementedError


class PathReader(NeatReader):
    def __init__(self, path: Path):
        self.path = path
        self._io: TextIO | None = None

    @property
    def name(self) -> str:
        return self.path.name

    def read_text(self) -> str:
        return self.path.read_text()

    def read_bytes(self) -> bytes:
        return self.path.read_bytes()

    def size(self) -> int:
        return self.path.stat().st_size

    def iterate(self, chunk_size: int) -> Iterable[str]:
        with self.path.open(mode="r") as f:
            while chunk := f.read(chunk_size):
                yield chunk

    def __enter__(self) -> TextIO:
        file = self.path.open(mode="r")
        self._io = file
        return file

    def __exit__(self) -> None:
        if self._io:
            self._io.close()

    def __str__(self) -> str:
        return self.path.as_posix()

    def exists(self) -> bool:
        return self.path.exists()

    def materialize_path(self) -> Path:
        return self.path


class HttpFileReader(NeatReader):
    def __init__(self, url: str, path: str):
        self._url = url
        self.path = path

    @property
    def name(self) -> str:
        if "/" in self.path:
            return self.path.rsplit("/", maxsplit=1)[-1]
        return self.path

    def read_text(self) -> str:
        response = requests.get(self._url)
        response.raise_for_status()
        return response.text

    def read_bytes(self) -> bytes:
        response = requests.get(self._url)
        response.raise_for_status()
        return response.content

    def size(self) -> int:
        response = requests.head(self._url)
        response.raise_for_status()
        return int(response.headers["Content-Length"])

    def iterate(self, chunk_size: int) -> Iterable[str]:
        with requests.get(self._url, stream=True) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size):
                yield chunk.decode("utf-8")

    def __enter__(self) -> IO:
        return StringIO(self.read_text())

    def __str__(self) -> str:
        return self._url

    def exists(self) -> bool:
        response = requests.head(self._url)
        return 200 <= response.status_code < 400

    def materialize_path(self) -> Path:
        path = Path(tempfile.gettempdir()).resolve() / "neat" / self.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.read_bytes())
        return path


class GitHubReader(HttpFileReader):
    raw_url = "https://raw.githubusercontent.com/"

    def __init__(self, raw: str):
        self.raw = raw
        self.repo, path = self._parse_url(raw)
        super().__init__(f"{self.raw_url}{self.repo}/main/{path}", path)

    @staticmethod
    def _parse_url(url: str) -> tuple[str, str]:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise NeatValueError(f"Unsupported scheme: {parsed.scheme}")

        path = parsed.path.lstrip("/")
        if parsed.netloc == "github.com":
            repo, path = path.split("/blob/main/", maxsplit=1)
            return repo, path

        elif parsed.netloc == "api.github.com":
            repo, path = path.removeprefix("repos/").split("/contents/", maxsplit=1)
            return repo, path

        elif parsed.netloc == "raw.githubusercontent.com":
            repo, path = path.split("/main/", maxsplit=1)
            return repo, path

        raise NeatValueError(f"Unsupported netloc: {parsed.netloc}")

    def __str__(self) -> str:
        return self.raw
