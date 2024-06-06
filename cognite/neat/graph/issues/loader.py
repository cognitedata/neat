from abc import ABC
from dataclasses import dataclass
from typing import Any

from cognite.neat.issues import NeatIssue

__all__ = [
    "LoaderIssue",
    "InvalidInstanceError",
]


@dataclass(frozen=True)
class LoaderIssue(NeatIssue, ABC): ...


@dataclass(frozen=True)
class InvalidInstanceError(LoaderIssue):
    description = "The {type_} with identifier {identifier} is invalid and will be skipped. {reason}"
    fix = "Check the error message and correct the instance."

    type_: str
    identifier: str
    reason: str

    def message(self) -> str:
        return self.description.format(type_=self.type_, identifier=self.identifier, reason=self.reason)

    def dump(self) -> dict[str, Any]:
        return {"error": type(self).__name__, "type": self.type_, "identifier": self.identifier, "reason": self.reason}
