from pathlib import Path
from typing import Any, Literal, overload

import yaml

from cognite.neat.issues import IssueList, NeatIssue
from cognite.neat.issues.errors import (
    FileMissingRequiredFieldError,
    FileNotAFileError,
    NeatFileNotFoundError,
    UnexpectedFileTypeError,
)
from cognite.neat.issues.neat_warnings.general import NeatValueWarning
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
        read_issues: list[NeatIssue] | None = None,
        filepaths: list[Path] | None = None,
    ) -> None:
        self.raw_data = raw_data
        self._read_issues = IssueList(read_issues)
        self._filepaths = filepaths

    @classmethod
    def from_file(cls, filepath: Path):
        if not filepath.exists():
            return cls({}, [NeatFileNotFoundError(filepath)])
        elif not filepath.is_file():
            return cls({}, [FileNotAFileError(filepath)])
        elif filepath.suffix not in [".yaml", ".yml"]:
            return cls({}, [UnexpectedFileTypeError(filepath, frozenset([".yaml", ".yml"]))])
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
        if self._read_issues.has_errors or not self.raw_data:
            if errors == "raise":
                raise self._read_issues.as_errors()
            return None, self._read_issues
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
            if errors == "raise":
                raise self._read_issues.as_errors()
            return None, self._read_issues

        metadata = self.raw_data["metadata"]

        if "role" not in metadata:
            self._read_issues.append(FileMissingRequiredFieldError(metadata, "metadata", "role"))
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
