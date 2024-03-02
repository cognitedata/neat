from pathlib import Path

import pytest
from pydantic.version import VERSION

from cognite.neat.rules.importers import ExcelImporter
from cognite.neat.rules.importers import _models as issue_cls
from tests.config import DOC_KNOWLEDGE_ACQUISITION_TUTORIAL
from tests.tests_unit.rules.test_importers.constants import DATA_DIR


def valid_rules_filepaths():
    yield pytest.param(DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "cdf-dms-architect-alice.xlsx", id="Alice rules")


def invalid_rules_filepaths():
    yield pytest.param(
        DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "not-existing.xlsx",
        issue_cls.SpreadsheetNotFound("not-existing.xlsx"),
        id="Not existing file",
    )
    major, minor, *_ = VERSION.split(".")

    yield pytest.param(
        DATA_DIR / "invalid_dms_rules.xlsx",
        issue_cls.InvalidPropertySpecification(
            column="IsList",
            row=4,
            type="bool_parsing",
            msg="Input should be a valid boolean, unable to interpret input",
            input="Apple",
            url=f"https://errors.pydantic.dev/{major}.{minor}/v/bool_parsing",
        ),
        id="Invalid property in Metadata sheet",
    )


class TestExcelImporter:
    @pytest.mark.parametrize("filepath", valid_rules_filepaths())
    def test_import_valid_rules(self, filepath: Path):
        importer = ExcelImporter(filepath)

        rules = importer.to_rules()

        assert rules

    @pytest.mark.parametrize("filepath, expected_issue", invalid_rules_filepaths())
    def test_import_invalid_rules_single_issue(self, filepath: Path, expected_issue: issue_cls.Error):
        importer = ExcelImporter(filepath)

        _, issues = importer.to_rules(errors="continue")

        assert len(issues) == 1
        assert issues[0] == expected_issue
