from dataclasses import dataclass
from typing import Any

from cognite.neat.issues import NeatError

__all__ = [
    "InvalidInstanceError",
]


@dataclass(frozen=True)
class InvalidInstanceError(NeatError):
    description = "The {type_} with identifier {identifier} is invalid and will be skipped. {reason}"
    fix = "Check the error message and correct the instance."

    type_: str
    identifier: str
    reason: str

    def message(self) -> str:
        return self.description.format(type_=self.type_, identifier=self.identifier, reason=self.reason)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["type"] = self.type_
        output["identifier"] = self.identifier
        output["reason"] = self.reason
        return output
