from dataclasses import dataclass

from cognite.neat.issues import NeatWarning


@dataclass(frozen=True)
class NeatValueWarning(NeatWarning):
    """{value}"""

    value: str


@dataclass(frozen=True)
class NotSupportedWarning(NeatWarning):
    """{feature} is not supported"""

    feature: str
