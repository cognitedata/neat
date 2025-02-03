from dataclasses import dataclass

from cognite.neat._issues import NeatError


@dataclass(unsafe_hash=True)
class NeatValueError(NeatError, ValueError):
    """{raw_message}"""

    raw_message: str


@dataclass(unsafe_hash=True)
class NeatTypeError(NeatError, TypeError):
    """{raw_message}"""

    raw_message: str


@dataclass(unsafe_hash=True)
class RegexViolationError(NeatError, ValueError):
    """The value '{value}' failed regex, {regex}, validation in {location}.
    Make sure that the name follows the regex pattern."""

    value: str
    regex: str
    location: str


@dataclass(unsafe_hash=True)
class NeatImportError(NeatError, ImportError):
    """The functionality requires {module}. You can include it
    in your neat installation with `pip install "cognite-neat[{neat_extra}]"`.
    """

    module: str
    neat_extra: str
