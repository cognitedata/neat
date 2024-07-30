from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cognite.neat.issues import NeatWarning
from cognite.neat.utils.text import humanize_sequence


@dataclass(frozen=True)
class FileMissingRequiredFieldWarning(NeatWarning):
    """Missing required {field_name} in {filepath}: {field}. The file will be skipped"""

    filepath: Path
    field_name: str
    field: str

    def message(self) -> str:
        return (self.__doc__ or "").format(field_name=self.field_name, field=self.field, filepath=self.filepath)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["field_name"] = self.field_name
        output["field"] = self.field
        output["filepath"] = self.filepath
        return output


@dataclass(frozen=True)
class UnexpectedFileTypeWarning(NeatWarning):
    """Unexpected file type: {filepath}. Expected format: {expected_format}"""

    extra = "Error: {error_message}"

    filepath: Path
    expected_format: list[str]
    error_message: str | None = None

    def message(self) -> str:
        msg = (__doc__ or "").format(
            filepath=repr(self.filepath), expected_format=humanize_sequence(self.expected_format)
        )
        if self.error_message:
            msg += f" {self.extra.format(error_message=self.error_message)}"
        return msg

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["filepath"] = self.filepath
        output["expected_format"] = self.expected_format
        return output


@dataclass(frozen=True)
class UnknownItemWarning(NeatWarning):
    """Unknown item {item} in {filepath}. The item will be skipped"""

    item: str
    filepath: Path

    def message(self) -> str:
        return (self.__doc__ or "").format(item=self.item, filepath=self.filepath)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["item"] = self.item
        output["filepath"] = self.filepath
        return output
