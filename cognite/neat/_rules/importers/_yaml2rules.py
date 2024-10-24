from pathlib import Path
from typing import Any, cast

import yaml

from cognite.neat._issues import IssueList, NeatIssue
from cognite.neat._issues.errors import (
    FileMissingRequiredFieldError,
    FileNotAFileError,
    FileNotFoundNeatError,
    FileTypeUnexpectedError,
)
from cognite.neat._issues.warnings import NeatValueWarning
from cognite.neat._rules._shared import ReadRules, T_InputRules
from cognite.neat._rules.models import INPUT_RULES_BY_ROLE, RoleTypes

from ._base import BaseImporter


class YAMLImporter(BaseImporter[T_InputRules]):
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
            return cls({}, [FileNotFoundNeatError(filepath)])
        elif not filepath.is_file():
            return cls({}, [FileNotAFileError(filepath)])
        elif filepath.suffix not in [".yaml", ".yml"]:
            return cls({}, [FileTypeUnexpectedError(filepath, frozenset([".yaml", ".yml"]))])
        return cls(yaml.safe_load(filepath.read_text()), filepaths=[filepath])

    def to_rules(self) -> ReadRules[T_InputRules]:
        if self._read_issues.has_errors or not self.raw_data:
            return ReadRules(None, self._read_issues, {})
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
            return ReadRules(None, self._read_issues, {})

        metadata = self.raw_data["metadata"]

        if "role" not in metadata:
            self._read_issues.append(FileMissingRequiredFieldError(metadata, "metadata", "role"))
            return ReadRules(None, self._read_issues, {})

        role_input = RoleTypes(metadata["role"])
        role_enum = RoleTypes(role_input)
        rules_cls = INPUT_RULES_BY_ROLE[role_enum]

        rules = cast(T_InputRules, rules_cls.load(self.raw_data))

        return ReadRules(rules, issue_list, {})
