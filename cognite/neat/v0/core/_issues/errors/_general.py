from dataclasses import dataclass
from typing import Literal

from cognite.neat.v0.core._issues import NeatError


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


@dataclass(unsafe_hash=True)
class WillExceedLimitError(NeatError, RuntimeError):
    """Cannot write {resource_count} {resource_type} to project {project} as the current available capacity
    is {available_capacity} {resource_type}. Neat requires a capacity of at least {margin} {resource_type} are
    left for future writes, {available_capacity}-{resource_count} < {margin}."""

    resource_type: Literal["instances"]
    resource_count: int
    project: str
    available_capacity: int
    margin: int
