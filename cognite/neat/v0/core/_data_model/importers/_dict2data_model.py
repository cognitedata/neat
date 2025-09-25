from pathlib import Path
from typing import Any, cast

import yaml

from cognite.neat.v0.core._data_model._shared import (
    ImportedDataModel,
    T_UnverifiedDataModel,
)
from cognite.neat.v0.core._data_model.models import (
    UNVERIFIED_DATA_MODEL_BY_ROLE,
    RoleTypes,
)
from cognite.neat.v0.core._issues import IssueList, MultiValueError, NeatIssue
from cognite.neat.v0.core._issues.errors import (
    FileMissingRequiredFieldError,
    FileReadError,
)
from cognite.neat.v0.core._issues.warnings import NeatValueWarning

from ._base import BaseImporter
from ._base_file_reader import BaseFileReader


class YAMLReader:
    """Handles reading and parsing YAML files with error handling."""

    @staticmethod
    def read_file(
        filepath: Path, allowed_extensions: frozenset[str] = frozenset([".yaml", ".yml"])
    ) -> tuple[dict[str, Any], list[NeatIssue]]:
        """Read a YAML file and return the data with any issues encountered."""
        issues = BaseFileReader.validate_file(filepath, allowed_extensions)
        if issues:
            return {}, issues
        # Try to load the YAML
        try:
            data = yaml.safe_load(filepath.read_text())
            if not isinstance(data, dict):
                issues.append(FileReadError(filepath, "YAML content is not a dictionary"))
                return {}, issues
            return data, issues
        except yaml.YAMLError as exc:
            return {}, [FileReadError(filepath, f"Invalid YAML: {exc!s}")]
        except Exception as exc:
            return {}, [FileReadError(filepath, f"Error reading file: {exc!s}")]


class DictImporter(BaseImporter[T_UnverifiedDataModel]):
    """Imports the data model from a YAML file.

    Args:
        raw_data: The raw data to be imported.

    .. note::

        YAML files are typically used for storing data model when checked into version
        control systems, e.g., git-history.
        The advantage of using YAML files over Excel is that tools like git can
        show the differences between different
        versions of the data model.

    """

    def __init__(
        self,
        raw_data: dict[str, Any],
        read_issues: list[NeatIssue] | None = None,
        filepaths: list[Path] | None = None,
        source_name: str = "Unknown",
    ) -> None:
        self.raw_data = raw_data
        self._read_issues = IssueList(read_issues)
        self._filepaths = filepaths
        self._source_name = source_name

    @property
    def description(self) -> str:
        return f"YAML file {self._source_name} read as unverified data model"

    @classmethod
    def from_yaml_file(cls, filepath: Path, source_name: str = "Unknown") -> "DictImporter":
        """Create a DictImporter from a YAML file."""
        data, issues = YAMLReader.read_file(filepath)

        if issues:
            return cls({}, issues)

        return cls(data, filepaths=[filepath], source_name=source_name)

    def to_data_model(self) -> ImportedDataModel[T_UnverifiedDataModel]:
        if self._read_issues.has_errors or not self.raw_data:
            self._read_issues.trigger_warnings()
            raise MultiValueError(self._read_issues.errors)

        issue_list = IssueList(title="YAML Importer", issues=self._read_issues)

        if not self._filepaths:
            issue_list.append(
                NeatValueWarning(
                    f"{type(self).__name__} was called without filepaths when there is content",
                )
            )
            metadata_file = Path()
        else:
            metadata_file_nullable = next((file for file in self._filepaths if file.stem == "metadata"), None)
            metadata_file = metadata_file_nullable or self._filepaths[0]

        if "metadata" not in self.raw_data:
            self._read_issues.append(FileMissingRequiredFieldError(metadata_file, "section", "metadata"))
            issue_list.trigger_warnings()
            raise MultiValueError(self._read_issues.errors)

        metadata = self.raw_data["metadata"]

        if "role" not in metadata:
            self._read_issues.append(FileMissingRequiredFieldError(metadata, "metadata", "role"))
            issue_list.trigger_warnings()
            raise MultiValueError(self._read_issues.errors)

        role_input = RoleTypes(metadata["role"])
        role_enum = RoleTypes(role_input)
        data_model_cls = UNVERIFIED_DATA_MODEL_BY_ROLE[role_enum]

        data_model = cast(T_UnverifiedDataModel, data_model_cls.load(self.raw_data))

        issue_list.trigger_warnings()
        if self._read_issues.has_errors:
            raise MultiValueError(self._read_issues.errors)

        return ImportedDataModel[T_UnverifiedDataModel](data_model)
