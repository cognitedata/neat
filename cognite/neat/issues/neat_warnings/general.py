from dataclasses import dataclass
from typing import Any

from cognite.neat.issues import NeatWarning


@dataclass(frozen=True)
class NeatValueWarning(NeatWarning):
    """{value}"""

    value: str

    def message(self) -> str:
        return self.value

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["value"] = self.value
        return output
