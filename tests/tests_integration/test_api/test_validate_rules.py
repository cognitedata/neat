from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
import yaml

from cognite.neat.core._client import NeatClient
from cognite.neat.core._issues import catch_issues
from cognite.neat.core._rules.importers import YAMLImporter
from cognite.neat.core._rules.transformers import VerifyDMSRules
from tests.data import SchemaData


class TestValidate:
    @pytest.mark.parametrize(
        "rule_filepath, expected_issues",
        [pytest.param(rules, issues, id=rules.stem) for rules, issues in SchemaData.PhysicalYamls.iterate()],
    )
    def test_validate_dms_rules(
        self, rule_filepath: Path, expected_issues: Path | None, neat_client: NeatClient
    ) -> None:
        with catch_issues() as issues:
            rules = YAMLImporter.from_file(rule_filepath, source_name=rule_filepath.name).to_rules()
            _ = VerifyDMSRules(validate=True, client=neat_client).transform(rules)

        if expected_issues is None:
            # If there are no issues, then this model should read without any errors or warnings.
            assert not issues.has_errors
            assert not issues.has_warnings
        else:
            actual = list(self._clean_issues(issue.dump() for issue in sorted(issues)))

            expected = yaml.safe_load(expected_issues.read_text())
            assert actual == expected, f"Expected issues: {expected}, but got:\n{yaml.safe_dump(actual)}"

    @staticmethod
    def _clean_issues(issues: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
        for issue in issues:
            # Filepaths are absolute and will differ between runs
            issue.pop("filepath", None)
            yield issue
