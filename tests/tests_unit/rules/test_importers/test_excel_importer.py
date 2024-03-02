from pathlib import Path

import pytest

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

    yield pytest.param(
        DATA_DIR / "invalid_dms_rules.xlsx",
        issue_cls.MetadataSheetMissingOrFailed(),
        id="Invalid propery in Metadata sheet",
    )


class TestExcelImporter:
    @pytest.mark.parametrize("filepath", valid_rules_filepaths())
    def test_import_valid_rules(self, filepath: Path):
        importer = ExcelImporter(filepath)

        rules = importer.to_rules()

        assert rules

    @pytest.mark.parametrize("filepath, expected_issue", invalid_rules_filepaths())
    def test_import_invalid_rules_single_issue(self, filepath: Path, expected_issue: issue_cls.ValidationError):
        importer = ExcelImporter(filepath)

        _, issues = importer.to_rules(errors="continue")

        assert len(issues) == 1
        assert issues[0] == expected_issue
