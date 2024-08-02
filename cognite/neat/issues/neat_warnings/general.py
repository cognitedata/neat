from dataclasses import dataclass
from typing import Any

from cognite.neat.issues import NeatWarning


@dataclass(frozen=True)
class NeatValueWarning(NeatWarning):
    """{value}"""

    value: str

    def as_message(self) -> str:
        return (self.__doc__ or "").format(value=self.value)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["value"] = self.value
        return output


@dataclass(frozen=True)
class NotSupportedWarning(NeatWarning):
    """{feature} is not supported"""

    feature: str

    def as_message(self) -> str:
        return (self.__doc__ or "").format(feature=self.feature)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["feature"] = self.feature
        return output
