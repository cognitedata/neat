from dataclasses import dataclass
from pathlib import Path

from yaml import YAMLError

from cognite.neat.issues import NeatError


@dataclass(frozen=True)
class FailedAuthorizationError(NeatError):
    """Missing authorization for {action}: {reason}"""

    action: str
    reason: str


@dataclass(frozen=True)
class FileReadError(NeatError):
    """Error when reading file, {filepath}: {reason}"""

    fix = "Is the {filepath} open in another program? Is the file corrupted?"
    filepath: Path
    reason: str


@dataclass(frozen=True)
class NeatFileNotFoundError(NeatError):
    """File {filepath} not found"""

    fix = "Make sure to provide a valid file"
    filepath: Path

    def as_exception(self) -> Exception:
        return FileNotFoundError(self.as_message())


@dataclass(frozen=True)
class FileMissingRequiredFieldError(NeatError):
    """Missing required {field_name} in {filepath}: {field}"""

    filepath: Path
    field_name: str
    field: str


@dataclass(frozen=True)
class InvalidYamlError(NeatError):
    """Invalid YAML: {reason}"""

    extra = "Expected format: {expected_format}"
    fix = "Check if the file is a valid YAML file"

    reason: str
    expected_format: str | None = None

    def as_exception(self) -> YAMLError:
        return YAMLError(self.as_message())


@dataclass(frozen=True)
class UnexpectedFileTypeError(NeatError):
    """Unexpected file type: {filepath}. Expected format: {expected_format}"""

    filepath: Path
    expected_format: frozenset[str]

    def as_exception(self) -> Exception:
        return TypeError(self.as_message())


@dataclass(frozen=True)
class FileNotAFileError(NeatError):
    """{filepath} is not a file"""

    fix = "Make sure to provide a valid file"
    filepath: Path

    def as_exception(self) -> Exception:
        return FileNotFoundError(self.as_message())
