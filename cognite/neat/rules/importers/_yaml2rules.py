from pathlib import Path
from typing import Any, Literal, overload

import yaml

from cognite.neat.rules import issues
from cognite.neat.rules.issues import IssueList, NeatValidationError, ValidationIssue
from cognite.neat.rules.models import RULES_PER_ROLE, DMSRules, RoleTypes
from cognite.neat.rules.models.dms import DMSRulesInput

from ._base import BaseImporter, Rules, _handle_issues


class YAMLImporter(BaseImporter):
    """Imports the rules from a YAML file.

    Args:
        raw_data: The raw data to be imported.

    .. note::

        YAML files are typically used for storing rules when checked into version control systems, e.g., git-history.
        The advantage of using YAML files over Excel is that tools like git can show the differences between different
        versions of the rules.

    """

    def __init__(
        self,
        raw_data: dict[str, Any],
        read_issues: list[ValidationIssue] | None = None,
        filepaths: list[Path] | None = None,
    ) -> None:
        self.raw_data = raw_data
        self._read_issues = IssueList(read_issues)
        self._filepaths = filepaths

    @classmethod
    def from_file(cls, filepath: Path):
        if not filepath.exists():
            return cls({}, [issues.fileread.FileNotFoundError(filepath)])
        if not filepath.is_file():
            return cls({}, [issues.fileread.FileNotAFileError(filepath)])
        elif filepath.suffix not in [".yaml", ".yml"]:
            return cls({}, [issues.fileread.InvalidFileFormatError(filepath, [".yaml", ".yml"])])
        return cls(yaml.safe_load(filepath.read_text()), filepaths=[filepath])

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules: ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList]: ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
        if any(issue for issue in self._read_issues if isinstance(issue, NeatValidationError)) or not self.raw_data:
            if errors == "raise":
                raise self._read_issues.as_errors()
            return None, self._read_issues
        issue_list = IssueList(title="YAML Importer", issues=self._read_issues)

        if not self._filepaths:
            issue_list.append(
                issues.fileread.BugInImporterWarning(
                    importer_name=type(self).__name__, error="No filepaths when there is content", filepath=Path()
                )
            )
            metadata_file = Path()
        else:
            metadata_file_nullable = next((file for file in self._filepaths if file.stem == "metadata"), None)
            metadata_file = metadata_file_nullable or self._filepaths[0]

        if "metadata" not in self.raw_data:
            self._read_issues.append(
                issues.spreadsheet_file.MetadataSheetMissingOrFailedError(metadata_file, "Metadata not found in file")
            )
            if errors == "raise":
                raise self._read_issues.as_errors()
            return None, self._read_issues

        metadata = self.raw_data["metadata"]

        if "role" not in metadata:
            self._read_issues.append(
                issues.spreadsheet_file.MetadataSheetMissingOrFailedError(metadata_file, "Role not found in metadata")
            )
            if errors == "raise":
                raise self._read_issues.as_errors()
            return None, self._read_issues

        role_input = RoleTypes(metadata["role"])
        role_enum = RoleTypes(role_input)
        rules_model = RULES_PER_ROLE[role_enum]

        with _handle_issues(issue_list) as future:
            rules: Rules
            if rules_model is DMSRules:
                rules = DMSRulesInput.load(self.raw_data).as_rules()
            else:
                rules = rules_model.model_validate(self.raw_data)

        if future.result == "failure":
            if errors == "continue":
                return None, issue_list
            else:
                raise issue_list.as_errors()

        return self._to_output(rules, issue_list, errors, role)
