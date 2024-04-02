from pathlib import Path

import pytest
from cognite.client.data_classes.data_modeling import ContainerId, ViewId
from pydantic.version import VERSION

import cognite.neat.rules.issues.spreadsheet
import cognite.neat.rules.issues.spreadsheet_file
from cognite.neat.rules import issues as validation
from cognite.neat.rules.importers import ExcelImporter
from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models._rules import DMSRules, InformationRules
from tests.config import DOC_RULES
from tests.tests_unit.rules.test_importers.constants import EXCEL_IMPORTER_DATA


def valid_dms_rules_filepaths():
    yield pytest.param(DOC_RULES / "cdf-dms-architect-alice.xlsx", DMSRules, False, id="Alice rules")
    yield pytest.param(DOC_RULES / "information-analytics-olav.xlsx", InformationRules, False, id="Olav user rules")
    yield pytest.param(DOC_RULES / "information-analytics-olav.xlsx", InformationRules, True, id="Olav reference rules")


def invalid_rules_filepaths():
    yield pytest.param(
        DOC_RULES / "not-existing.xlsx",
        IssueList(
            [cognite.neat.rules.issues.spreadsheet_file.SpreadsheetNotFoundError(DOC_RULES / "not-existing.xlsx")]
        ),
        id="Not existing file",
    )
    major, minor, *_ = VERSION.split(".")

    yield pytest.param(
        EXCEL_IMPORTER_DATA / "invalid_property_dms_rules.xlsx",
        IssueList(
            [
                validation.spreadsheet.InvalidPropertyError(
                    column="IsList",
                    row=5,
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
        EXCEL_IMPORTER_DATA / "inconsistent_container_dms_rules.xlsx",
        IssueList(
            [
                cognite.neat.rules.issues.spreadsheet.MultiValueTypeError(
                    container=ContainerId("neat", "Flowable"),
                    property_name="maxFlow",
                    row_numbers={4, 5},
                    value_types={"float32", "float64"},
                )
            ]
        ),
        id="Inconsistent container",
    )
    yield pytest.param(
        EXCEL_IMPORTER_DATA / "missing_view_container_dms_rules.xlsx",
        IssueList(
            [
                cognite.neat.rules.issues.spreadsheet.NonExistingViewError(
                    column="View",
                    row=4,
                    type="value_error.missing",
                    view_id=ViewId("neat", "Pump", "1"),
                    msg="",
                    input=None,
                    url=None,
                ),
                cognite.neat.rules.issues.spreadsheet.NonExistingContainerError(
                    column="Container",
                    row=4,
                    type="value_error.missing",
                    container_id=ContainerId("neat", "Pump"),
                    msg="",
                    input=None,
                    url=None,
                ),
            ]
        ),
        id="Missing container and view definition",
    )


class TestExcelImporter:
    @pytest.mark.parametrize("filepath, rule_type, is_reference", valid_dms_rules_filepaths())
    def test_import_valid_rules(self, filepath: Path, rule_type: DMSRules | InformationRules, is_reference: bool):
        importer = ExcelImporter(filepath)
        rules = importer.to_rules(errors="raise", is_reference=is_reference)
        assert isinstance(rules, rule_type)

    @pytest.mark.parametrize("filepath, expected_issues", invalid_rules_filepaths())
    def test_import_invalid_rules(self, filepath: Path, expected_issues: IssueList):
        importer = ExcelImporter(filepath)

        _, issues = importer.to_rules(errors="continue")

        assert len(issues) == len(expected_issues)
        assert sorted(issues) == sorted(expected_issues)
