from pathlib import Path

import pytest
import yaml

from cognite.neat._client import NeatClient
from cognite.neat._issues import catch_issues
from cognite.neat._rules.importers import YAMLImporter
from cognite.neat._rules.transformers import VerifyDMSRules
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
            assert not issues.has_errors
            assert not issues.has_warnings
        else:
            actual = [issue.dump() for issue in sorted(issues)]
            expected = yaml.safe_load(expected_issues.read_text())
            assert actual == expected, f"Expected issues: {expected}, but got: {actual}"
