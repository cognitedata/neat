from abc import ABC
from dataclasses import dataclass
from pathlib import Path

from .base import NeatValidationError, ValidationWarning

__all__ = [
    "FileReadWarning",
    "InvalidFileFormatWarning",
    "UnsupportedSpecWarning",
    "UnknownItemWarning",
    "FailedLoadWarning",
    "BugInImporterWarning",
    "FileReadError",
    "FileNotFoundError",
    "FileNotAFileError",
    "InvalidFileFormatError",
    "FailedStringLoadError",
]


@dataclass(frozen=True)
class FileReadError(NeatValidationError, ABC):
    description = "An error was raised during reading."
    fix = "No fix is available."

    filepath: Path

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["filepath"] = str(self.filepath)
        return output


@dataclass(frozen=True)
class FileReadWarning(ValidationWarning, ABC):
    description = "A warning was raised during reading."
    fix = "No fix is available."

    filepath: Path

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["filepath"] = str(self.filepath)
        return output


@dataclass(frozen=True)
class InvalidFileFormatWarning(FileReadWarning):
    description = "The file format is invalid"
    fix = "Check if the file format is supported."

    reason: str

    def message(self) -> str:
        return f"Skipping invalid file {self.filepath.name}: {self.reason}"

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["reason"] = self.reason
        return output


@dataclass(frozen=True)
class UnsupportedSpecWarning(FileReadWarning):
    description = "The spec in the file is not supported"
    fix = "Change to an supported spec"

    spec_name: str
    version: str | None = None

    def message(self) -> str:
        if self.version:
            suffix = f"{self.spec_name} v{self.version} is not supported."
        else:
            suffix = f"{self.spec_name} is not supported."
        return f"Skipping file {self.filepath.name}: {suffix}. {self.fix}"

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["spec_name"] = self.spec_name
        output["version"] = self.version
        return output


@dataclass(frozen=True)
class UnknownItemWarning(FileReadWarning):
    description = "The file is missing an implementation"
    fix = "Check if the file is supported. If not, contact the neat team on Github."

    reason: str

    def message(self) -> str:
        return f"Skipping file {self.filepath.name}: {self.reason}. {self.fix}"

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["reason"] = self.reason
        return output


@dataclass(frozen=True)
class FailedLoadWarning(FileReadWarning):
    description = "The file content is invalid"
    fix = "Check if the file content is valid"

    expected_format: str
    error_message: str

    def message(self) -> str:
        return (
            f"Failed to load {self.filepath.name}. Expected format: {self.expected_format}. Error: {self.error_message}"
        )

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["expected_format"] = self.expected_format
        output["error_message"] = self.error_message
        return output


@dataclass(frozen=True)
class BugInImporterWarning(FileReadWarning):
    description = "A bug was raised during reading."
    fix = "No fix is available. Contact the neat team on Github"

    importer_name: str
    error: str

    def message(self) -> str:
        return f"Bug in importer {self.importer_name} when reading {self.filepath.name}: {self.error}"

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["importer_name"] = self.importer_name
        output["error"] = self.error
        return output


@dataclass(frozen=True)
class FileNotFoundError(FileReadError):
    description = "The file was not found"
    fix = "Check if the file exists."

    def message(self) -> str:
        return f"File {self.filepath} was not found. {self.fix}"


@dataclass(frozen=True)
class FileNotAFileError(FileReadError):
    description = "The file is not a file"
    fix = "Check if the file exists."

    def message(self) -> str:
        return f"{self.filepath} is not a file. {self.fix}"


@dataclass(frozen=True)
class InvalidFileFormatError(FileReadError):
    description = "The file is not in the expected format"
    fix = "Check if the file is in the expected format"

    expected_format: list[str]

    def message(self) -> str:
        return f"{self.filepath} is not in the expected format. Expected format: {self.expected_format}."


@dataclass(frozen=True)
class FailedStringLoadError(NeatValidationError):
    description = "The file content is invalid"
    fix = "Check if the file content is valid"

    expected_format: str
    error_message: str

    def message(self) -> str:
        return f"Failed to load string. Expected format: {self.expected_format}. Error: {self.error_message}"

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["expected_format"] = self.expected_format
        output["error_message"] = self.error_message
        return output


@dataclass(frozen=True)
class NoFilesFoundError(FileReadError):
    description = "No files were found in the directory"
    fix = "Check if the directory contains files"

    expected_formats: list[str] | None = None

    def message(self) -> str:
        if self.expected_formats:
            return f"No files were found in {self.filepath.name}. Expected format: {self.expected_formats}. {self.fix}"
        return f"No files were found in {self.filepath.name}. {self.fix}"
