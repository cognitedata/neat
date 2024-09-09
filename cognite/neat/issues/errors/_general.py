from dataclasses import dataclass

from cognite.neat.issues import NeatError


@dataclass(frozen=True)
class NeatValueError(NeatError, ValueError):
    """{raw_message}"""

    raw_message: str


@dataclass(frozen=True)
class NeatTypeError(NeatError, TypeError):
    """{raw_message}"""

    raw_message: str


@dataclass(frozen=True)
class RegexViolationError(NeatError, ValueError):
    """Value, {value} failed regex, {regex}, validation. Make sure that the name follows the regex pattern."""

    value: str
    regex: str


@dataclass(frozen=True)
class NeatImportError(NeatError, ImportError):
    """The functionality requires {module}. You can include it
    in your neat installation with `pip install "cognite-neat[{neat_extra}]"`.
    """

    module: str
    neat_extra: str
