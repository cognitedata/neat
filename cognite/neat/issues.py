from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import total_ordering
from typing import Any, ClassVar


@total_ordering
@dataclass(frozen=True)
class NeatIssue(ABC):
    description: ClassVar[str]
    fix: ClassVar[str]

    def message(self) -> str:
        """Return a human-readable message for the issue.

        This is the default implementation, which returns the description.
        It is recommended to override this method in subclasses with a more
        specific message.
        """
        return self.description

    @abstractmethod
    def dump(self) -> dict[str, Any]:
        """Return a dictionary representation of the issue."""
        raise NotImplementedError()

    def __lt__(self, other: "NeatIssue") -> bool:
        if not isinstance(other, NeatIssue):
            return NotImplemented
        return (type(self).__name__, self.message()) < (type(other).__name__, other.message())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NeatIssue):
            return NotImplemented
        return (type(self).__name__, self.message()) == (type(other).__name__, other.message())
