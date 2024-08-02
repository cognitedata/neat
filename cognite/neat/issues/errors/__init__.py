from cognite.neat.issues import NeatError

from .external import (
    FailedAuthorizationError,
    FileMissingRequiredFieldError,
    FileReadError,
    InvalidYamlError,
    NeatFileNotFoundError,
)
from .general import MissingRequiredFieldError, NeatImportError, NeatValueError, RegexViolationError

__all__ = [
    "MissingRequiredFieldError",
    "NeatValueError",
    "NeatImportError",
    "RegexViolationError",
    "FailedAuthorizationError",
    "InvalidYamlError",
    "FileReadError",
    "NeatFileNotFoundError",
    "FileMissingRequiredFieldError",
]

_NEAT_ERRORS_BY_NAME = {error.__name__: error for error in NeatError.__subclasses__()}
