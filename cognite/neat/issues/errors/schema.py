from dataclasses import dataclass
from typing import Any

from cognite.neat.issues import NeatError


@dataclass(frozen=True)
class InvalidSheetError(NeatError):
    """The sheet {sheet_name} is not valid"""

    sheet_name: str

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["sheet_name"] = self.sheet_name
        return output
