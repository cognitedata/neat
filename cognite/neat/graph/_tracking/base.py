from abc import ABC, abstractmethod
from collections.abc import Sequence

from cognite.neat.issues import NeatIssue


class Tracker(ABC):
    def __init__(self, name: str, units: list[str], unit_type: str) -> None:
        self.name = name
        self.units = units
        self.unit_type = unit_type

    @abstractmethod
    def start(self, unit: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def finish(self, unit: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def _issue(self, issue: NeatIssue) -> None:
        raise NotImplementedError()

    def issue(self, issue: NeatIssue | Sequence[NeatIssue]) -> None:
        if isinstance(issue, NeatIssue):
            self._issue(issue)
            return
        for item in issue:
            self._issue(item)
