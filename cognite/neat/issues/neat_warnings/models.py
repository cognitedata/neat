from dataclasses import dataclass
from typing import Any

from cognite.neat.issues import NeatWarning


@dataclass(frozen=True)
class InvalidClassWarning(NeatWarning):
    description = "The class {class_name} is invalid and will be skipped. {reason}"
    fix = "Check the error message and correct the class."

    class_name: str
    reason: str

    def message(self) -> str:
        return self.description.format(class_name=self.class_name, reason=self.reason)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["class_name"] = self.class_name
        output["reason"] = self.reason
        return output
