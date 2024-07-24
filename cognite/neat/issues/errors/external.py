from dataclasses import dataclass
from typing import Any

from cognite.neat.issues import NeatError


@dataclass(frozen=True)
class FailedAuthorizationError(NeatError):
    description = "Missing authorization for {action}: {reason}"

    action: str
    reason: str

    def message(self) -> str:
        return self.description.format(action=self.action, reason=self.reason)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["action"] = self.action
        output["reason"] = self.reason
        return output
