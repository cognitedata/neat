from abc import ABC
from typing import IO, Any


class NeatIO(IO[str], ABC):
    @classmethod
    def create(cls, io: Any) -> "NeatIO":
        raise NotImplementedError()

    def __str__(self) -> str:
        raise NotImplementedError()
