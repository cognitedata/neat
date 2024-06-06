from abc import ABC, abstractmethod
from collections.abc import Sequence

from cognite.neat.issues import NeatIssue


class Tracker(ABC):
    def __init__(self, units: list[str]) -> None:
        self.units = units

    @abstractmethod
    def start(self, unit: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def finish(self, unit: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def issue(self, issue: NeatIssue | Sequence[NeatIssue]) -> None:
        raise NotImplementedError()
