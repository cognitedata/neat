from pathlib import Path

import pytest

from cognite.neat.rules.importers import ExcelImporter
from tests.config import DOC_KNOWLEDGE_ACQUISITION_TUTORIAL


def valid_rules_filepaths():
    yield pytest.param(DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "cdf-dms-architect-alice.xlsx", id="Alice rules")


class TestExcelImporter:
    @pytest.mark.parametrize("filepath", valid_rules_filepaths())
    def test_import_valid_rules(self, filepath: Path):
        importer = ExcelImporter(filepath)

        rules = importer.to_rules()

        assert rules
