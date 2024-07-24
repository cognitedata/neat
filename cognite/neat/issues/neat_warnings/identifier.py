from dataclasses import dataclass
from typing import Any

from cognite.neat.issues import NeatWarning


@dataclass(frozen=True)
class RegexViolationWarning(NeatWarning):
    """The value '{value}' of {identifier} does not match the {pattern_name} pattern '{pattern}'"""

    value: str
    pattern: str
    identifier: str
    pattern_name: str

    def message(self) -> str:
        return (self.__doc__ or "").format(
            value=self.value, pattern=self.pattern, identifier=self.identifier, pattern_name=self.pattern_name
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["value"] = self.value
        output["pattern"] = self.pattern
        output["identifier"] = self.identifier
        output["pattern_name"] = self.pattern_name
        return output
