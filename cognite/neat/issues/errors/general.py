from dataclasses import dataclass
from typing import Any

from cognite.neat.issues import NeatError


@dataclass(frozen=True)
class NeatValueError(NeatError, ValueError):
    """{raw_message}"""

    raw_message: str

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["rawMessage"] = self.raw_message
        return output
