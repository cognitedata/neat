from abc import ABC, abstractmethod
from collections.abc import Iterable
from io import StringIO
from pathlib import Path
from typing import IO, Any, TextIO
from urllib.parse import urlparse

import requests

from cognite.neat._issues.errors import NeatTypeError, NeatValueError


class NeatReader(ABC):
    @classmethod
    def create(cls, io: Any) -> "NeatReader":
        if isinstance(io, str):
            url = urlparse(io)
            if url.scheme == "https" and url.netloc.endswith("github.com"):
                return GitHubFile(io)

        if isinstance(io, str | Path):
            return NeatPath(Path(io))
        raise NeatTypeError(f"Unsupported type: {type(io)}")

    @abstractmethod
    def read(self) -> str:
        """Read the buffer as a string"""
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


class NeatPath(NeatReader):
    def __init__(self, path: Path):
        self.path = path
        self._io: TextIO | None = None

    def read(self) -> str:
        return self.path.read_text()

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

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._io:
            self._io.close()

    def __str__(self) -> str:
        return self.path.as_posix()


class GitHubFile(NeatReader):
    raw_url = "https://raw.githubusercontent.com/"

    def __init__(self, raw: str):
        self.raw = raw
        self.repo, self.path = self._parse_url(raw)

    @property
    def _full_url(self) -> str:
        return f"{self.raw_url}{self.repo}/main/{self.path}"

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

    def read(self) -> str:
        response = requests.get(self._full_url)
        response.raise_for_status()
        return response.text

    def size(self) -> int:
        response = requests.head(self._full_url)
        response.raise_for_status()
        return int(response.headers["Content-Length"])

    def iterate(self, chunk_size: int) -> Iterable[str]:
        with requests.get(self._full_url, stream=True) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size):
                yield chunk.decode("utf-8")

    def __enter__(self) -> IO:
        return StringIO(self.read())

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        pass
