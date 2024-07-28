from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cognite.neat.issues import NeatError


@dataclass(frozen=True)
class FailedAuthorizationError(NeatError):
    description = "Missing authorization for {action}: {reason}"

    action: str
    reason: str

    def message(self) -> str:
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

    def message(self) -> str:
        return self.description.format(filepath=repr(self.filepath), reason=self.reason)

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

    def message(self) -> str:
        return (__doc__ or "").format(filepath=repr(self.filepath))

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["filepath"] = self.filepath
        return output


@dataclass(frozen=True)
class FileMissingRequiredFieldError(NeatError):
    """Missing required {field_name} in {filepath}: {fields}"""

    filepath: Path
    field_name: str
    field: str

    def message(self) -> str:
        return self.description.format(field_name=self.field, filepath=repr(self.filepath), field_type=self.field_name)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["field"] = self.field
        output["filepath"] = self.filepath
        output["field_type"] = self.field_name
        return output
