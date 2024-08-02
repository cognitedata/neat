from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yaml import YAMLError

from cognite.neat.issues import NeatError
from cognite.neat.utils.text import humanize_sequence


@dataclass(frozen=True)
class FailedAuthorizationError(NeatError):
    description = "Missing authorization for {action}: {reason}"

    action: str
    reason: str

    def as_message(self) -> str:
        return self.description.format(action=self.action, reason=self.reason)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["action"] = self.action
        output["reason"] = self.reason
        return output


@dataclass(frozen=True)
class FileReadError(NeatError):
    """Error when reading file, {filepath}: {reason}"""

    fix = "Is the {filepath} open in another program? Is the file corrupted?"
    filepath: Path
    reason: str

    def as_message(self) -> str:
        return (self.__doc__ or "").format(filepath=repr(self.filepath), reason=self.reason)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["filepath"] = self.filepath
        output["reason"] = self.reason
        return output


@dataclass(frozen=True)
class NeatFileNotFoundError(NeatError):
    """File {filepath} not found"""

    fix = "Make sure to provide a valid file"
    filepath: Path

    def as_exception(self) -> Exception:
        return FileNotFoundError(self.as_message())

    def as_message(self) -> str:
        return (__doc__ or "").format(filepath=repr(self.filepath))

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["filepath"] = self.filepath
        return output


@dataclass(frozen=True)
class FileMissingRequiredFieldError(NeatError):
    """Missing required {field_name} in {filepath}: {field}"""

    filepath: Path
    field_name: str
    field: str

    def as_message(self) -> str:
        return (self.__doc__ or "").format(field_name=self.field_name, filepath=repr(self.filepath), field=self.field)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["field"] = self.field
        output["filepath"] = self.filepath
        output["field_type"] = self.field_name
        return output


@dataclass(frozen=True)
class InvalidYamlError(NeatError):
    """Invalid YAML: {reason}"""

    extra = "Expected format: {expected_format}"
    fix = "Check if the file is a valid YAML file"

    reason: str
    expected_format: str | None = None

    def as_exception(self) -> YAMLError:
        return YAMLError(self.as_message())

    def as_message(self) -> str:
        msg = (self.__doc__ or "").format(reason=self.reason)
        if self.expected_format:
            msg += f" {self.extra.format(expected_format=self.expected_format)}"
        return msg

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["reason"] = self.reason
        output["expected_format"] = self.expected_format
        return output


@dataclass(frozen=True)
class UnexpectedFileTypeError(NeatError):
    """Unexpected file type: {filepath}. Expected format: {expected_format}"""

    filepath: Path
    expected_format: list[str]

    def as_exception(self) -> Exception:
        return TypeError(self.as_message())

    def as_message(self) -> str:
        return (__doc__ or "").format(
            filepath=repr(self.filepath), expected_format=humanize_sequence(self.expected_format)
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["filepath"] = self.filepath
        output["expected_format"] = self.expected_format
        return output


@dataclass(frozen=True)
class FileNotAFileError(NeatError):
    """{filepath} is not a file"""

    fix = "Make sure to provide a valid file"
    filepath: Path

    def as_exception(self) -> Exception:
        return FileNotFoundError(self.as_message())

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["filepath"] = self.filepath
        return output
