from pathlib import Path
from typing import Protocol, TypeVar

from cognite.neat.v0.core._issues import NeatIssue
from cognite.neat.v0.core._issues.errors import (
    FileNotAFileError,
    FileNotFoundNeatError,
    FileTypeUnexpectedError,
)

T = TypeVar("T")
DataT = TypeVar("DataT", covariant=True)


class FileReader(Protocol[DataT]):
    """Protocol for file readers that parse files into structured data."""

    def read_file(self, filepath: Path) -> tuple[DataT, list[NeatIssue]]:
        """Read a file and return the data with any issues encountered.

        Args:
            filepath: Path to the file to read

        Returns:
            Tuple of (parsed_data, issues_list)
        """
        ...


class BaseFileReader:
    """Base implementation with common file validation logic."""

    @staticmethod
    def validate_file(filepath: Path, allowed_extensions: frozenset[str]) -> list[NeatIssue]:
        """Validate that a file exists and has the correct extension.

        Args:
            filepath: Path to the file to validate
            allowed_extensions: Set of allowed file extensions

        Returns:
            List of issues found during validation, empty if valid
        """
        # Check if file exists
        if not filepath.exists():
            return [FileNotFoundNeatError(filepath)]

        # Check if it's a file
        if not filepath.is_file():
            return [FileNotAFileError(filepath)]

        # Check file extension
        if filepath.suffix not in allowed_extensions:
            return [FileTypeUnexpectedError(filepath, allowed_extensions)]

        return []
