from dataclasses import dataclass

from cognite.neat.core._constants import DMS_INSTANCE_LIMIT_MARGIN
from cognite.neat.core._issues import NeatError


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
class WillExceedInstanceLimitError(NeatError, RuntimeError):
    """Cannot write {instance_count} instances to project {project} as the current available capacity
    is {available_capacity} instances. Neat requires a capacity of at least {margin} instances are
    left for future writes, {available_capacity}-{instance_count} < {margin}."""

    instance_count: int
    project: str
    available_capacity: int
    margin: int = DMS_INSTANCE_LIMIT_MARGIN
