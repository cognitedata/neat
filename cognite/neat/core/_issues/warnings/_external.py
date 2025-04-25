from dataclasses import dataclass
from pathlib import Path

from cognite.neat._issues import NeatWarning


@dataclass(unsafe_hash=True)
class FileReadWarning(NeatWarning):
    """Error when reading file, {filepath}: {reason}"""

    filepath: Path
    reason: str


@dataclass(unsafe_hash=True)
class FileMissingRequiredFieldWarning(NeatWarning):
    """Missing required {field_name} in {filepath}: {field}. The file will be skipped"""

    filepath: Path
    field_name: str
    field: str


@dataclass(unsafe_hash=True)
class FileTypeUnexpectedWarning(NeatWarning):
    """Unexpected file type: {filepath}. Expected format: {expected_format}"""

    extra = "Error: {error_message}"

    filepath: Path
    expected_format: frozenset[str]
    error_message: str | None = None


@dataclass(unsafe_hash=True)
class FileItemNotSupportedWarning(NeatWarning):
    """The item {item} in {filepath} is not supported. The item will be skipped"""

    item: str
    filepath: Path


@dataclass(unsafe_hash=True)
class CDFAuthWarning(NeatWarning):
    """Failed to {action}: {reason}"""

    action: str
    reason: str


@dataclass(unsafe_hash=True)
class CDFMaxIterationsWarning(NeatWarning):
    """The maximum number of iterations ({max_iterations}) has been reached. {message}"""

    message: str
    max_iterations: int
