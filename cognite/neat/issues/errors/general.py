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


@dataclass(frozen=True)
class RegexViolationError(NeatError):
    """Value, {value} failed regex, {regex}, validation. Make sure that the name follows the regex pattern."""

    value: str
    regex: str

    def dump(self) -> dict[str, str]:
        output = super().dump()
        output["value"] = self.value
        output["regex"] = self.regex
        return output

    def message(self) -> str:
        return (self.__doc__ or "").format(value=self.value, regex=self.regex)
