from dataclasses import dataclass

from cognite.neat.v0.core._issues import NeatWarning


@dataclass(unsafe_hash=True)
class NeatValueWarning(NeatWarning):
    """{value}"""

    value: str


@dataclass(unsafe_hash=True)
class NotSupportedWarning(NeatWarning):
    """{feature} is not supported"""

    feature: str


@dataclass(unsafe_hash=True)
class RegexViolationWarning(NeatWarning):
    """The value '{value}' of {identifier} does not match the {pattern_name} pattern '{pattern}'"""

    extra = "{motivation}"
    value: str
    pattern: str
    identifier: str
    pattern_name: str
    motivation: str | None = None


@dataclass(unsafe_hash=True)
class MissingCogniteClientWarning(NeatWarning):
    """Missing Cognite Client required for {functionality}"""

    functionality: str


@dataclass(unsafe_hash=True)
class DeprecatedWarning(NeatWarning):
    """{feature} is deprecated"""

    extra = "{replacement}"

    feature: str
    replacement: str | None = None
