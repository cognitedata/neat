from dataclasses import dataclass
from pathlib import Path

from yaml import YAMLError

from cognite.neat.issues import NeatError


@dataclass(frozen=True)
class FailedAuthorizationError(NeatError, RuntimeError):
    """Missing authorization for {action}: {reason}"""

    action: str
    reason: str


@dataclass(frozen=True)
class FileReadError(NeatError, RuntimeError):
    """Error when reading file, {filepath}: {reason}"""

    fix = "Is the {filepath} open in another program? Is the file corrupted?"
    filepath: Path
    reason: str


@dataclass(frozen=True)
class NeatFileNotFoundError(NeatError, FileNotFoundError):
    """File {filepath} not found"""

    fix = "Make sure to provide a valid file"
    filepath: Path


@dataclass(frozen=True)
class FileMissingRequiredFieldError(NeatError, ValueError):
    """Missing required {field_name} in {filepath}: {field}"""

    filepath: Path
    field_name: str
    field: str


@dataclass(frozen=True)
class InvalidYamlError(NeatError, YAMLError):
    """Invalid YAML: {reason}"""

    extra = "Expected format: {expected_format}"
    fix = "Check if the file is a valid YAML file"

    reason: str
    expected_format: str | None = None


@dataclass(frozen=True)
class UnexpectedFileTypeError(NeatError, TypeError):
    """Unexpected file type: {filepath}. Expected format: {expected_format}"""

    filepath: Path
    expected_format: frozenset[str]


@dataclass(frozen=True)
class FileNotAFileError(NeatError, FileNotFoundError):
    """{filepath} is not a file"""

    fix = "Make sure to provide a valid file"
    filepath: Path
