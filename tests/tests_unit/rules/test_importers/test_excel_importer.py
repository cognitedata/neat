from pathlib import Path

import pytest
from pydantic.version import VERSION

from cognite.neat.rules import validation
from cognite.neat.rules.importers import ExcelImporter
from cognite.neat.rules.models._rules import DMSRules
from cognite.neat.rules.validation import IssueList
from tests.config import DOC_KNOWLEDGE_ACQUISITION_TUTORIAL
from tests.tests_unit.rules.test_importers.constants import DATA_DIR


def valid_rules_filepaths():
    yield pytest.param(DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "cdf-dms-architect-alice.xlsx", id="Alice rules")


def invalid_rules_filepaths():
    yield pytest.param(
        DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "not-existing.xlsx",
        IssueList([validation.SpreadsheetNotFound("not-existing.xlsx")]),
        id="Not existing file",
    )
    major, minor, *_ = VERSION.split(".")

    yield pytest.param(
        DATA_DIR / "invalid_property_dms_rules.xlsx",
        IssueList(
            [
                validation.InvalidPropertySpecification(
                    column="IsList",
                    row=4,
                    type="bool_parsing",
                    msg="Input should be a valid boolean, unable to interpret input",
                    input="Apple",
                    url=f"https://errors.pydantic.dev/{major}.{minor}/v/bool_parsing",
                )
            ]
        ),
        id="Invalid property specification",
    )

    yield pytest.param(
        DATA_DIR / "inconsistent_container_dms_rules.xlsx",
        IssueList([]),
        id="Inconsistent container",
    )


class TestExcelImporter:
    @pytest.mark.parametrize("filepath", valid_rules_filepaths())
    def test_import_valid_rules(self, filepath: Path):
        importer = ExcelImporter(filepath)

        rules = importer.to_rules(errors="raise")

        assert isinstance(rules, DMSRules)

    @pytest.mark.parametrize("filepath, expected_issues", invalid_rules_filepaths())
    def test_import_invalid_rules_single_issue(self, filepath: Path, expected_issues: IssueList):
        importer = ExcelImporter(filepath)

        _, issues = importer.to_rules(errors="continue")

        assert len(issues) == len(expected_issues)
        assert sorted(issues) == sorted(expected_issues)
