from dataclasses import dataclass
from pathlib import Path

from cognite.neat.issues import NeatWarning


@dataclass(frozen=True)
class FileReadWarning(NeatWarning):
    """Error when reading file, {filepath}: {reason}"""

    filepath: Path
    reason: str


@dataclass(frozen=True)
class FileMissingRequiredFieldWarning(NeatWarning):
    """Missing required {field_name} in {filepath}: {field}. The file will be skipped"""

    filepath: Path
    field_name: str
    field: str


@dataclass(frozen=True)
class FileTypeUnexpectedWarning(NeatWarning):
    """Unexpected file type: {filepath}. Expected format: {expected_format}"""

    extra = "Error: {error_message}"

    filepath: Path
    expected_format: frozenset[str]
    error_message: str | None = None


@dataclass(frozen=True)
class FileItemNotSupportedWarning(NeatWarning):
    """The item {item} in {filepath} is not supported. The item will be skipped"""

    item: str
    filepath: Path
