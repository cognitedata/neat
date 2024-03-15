from abc import ABC
from dataclasses import dataclass
from pathlib import Path

from ._base import ValidationWarning


@dataclass(frozen=True, order=True)
class FileReadWarning(ValidationWarning, ABC):
    description = "A warning was raised during reading."
    fix = "No fix is available."

    filepath: Path

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["filepath"] = str(self.filepath)
        return output


@dataclass(frozen=True, order=True)
class InvalidFileFormat(FileReadWarning):
    description = "The file format is invalid"
    fix = "Check if the file format is supported."

    reason: str

    def message(self) -> str:
        return f"Skipping invalid file {self.filepath.name}: {self.reason}"

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["reason"] = self.reason
        return output


@dataclass(frozen=True, order=True)
class UnsupportedSpec(FileReadWarning):
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


@dataclass(frozen=True, order=True)
class UnknownItem(FileReadWarning):
    description = "The file is missing an implementation"
    fix = "Check if the file is supported. If not, contact the neat team on Github."

    reason: str

    def message(self) -> str:
        return f"Skipping file {self.filepath.name}: {self.reason}. {self.fix}"

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["reason"] = self.reason
        return output


@dataclass(frozen=True, order=True)
class BugInImporter(FileReadWarning):
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
