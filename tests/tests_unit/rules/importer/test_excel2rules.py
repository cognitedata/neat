import sys
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from cognite.neat.rules import importer
from cognite.neat.rules.importers._spreadsheet2rules import ExcelImporter
from cognite.neat.rules.issues import IssueList, SheetMissingError
from cognite.neat.rules.models import Tables
from cognite.neat.rules.models._rules import DomainRules, InformationRules
from cognite.neat.rules.models._rules.base import RoleTypes
from cognite.neat.rules.models.raw_rules import RawRules
from tests import config
from tests.config import DOC_KNOWLEDGE_ACQUISITION_TUTORIAL

if sys.version_info < (3, 11):
    pass


@pytest.fixture(scope="session")
def raw_rules() -> dict[str, pd.DataFrame]:
    return importer.ExcelImporter(config.TNT_TRANSFORMATION_RULES).to_raw_rules()


def test_raw_rules_validation(raw_rules):
    assert raw_rules.to_rules()


def generate_invalid_raw_rules_test_data():
    raw_tables = importer.ExcelImporter(config.TNT_TRANSFORMATION_RULES).to_tables()

    invalid_class_label = raw_tables
    invalid_class_label[Tables.properties] = invalid_class_label[Tables.properties].copy()
    invalid_class_label[Tables.properties].loc[0, "Class"] = "non existing class"
    yield pytest.param(invalid_class_label, id="Invalid mapping rule")


@pytest.mark.parametrize("raw_tables", generate_invalid_raw_rules_test_data())
def test_parse_transformation_invalid_rules(raw_tables: dict[str, pd.DataFrame]):
    with pytest.raises(ValidationError):
        RawRules.from_tables(raw_tables).to_rules()


class TestExcelImporter:
    @pytest.mark.parametrize(
        "filepath",
        [
            pytest.param(
                DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "expert-wind-energy-jon.xlsx", id="expert-wind-energy-jon"
            ),
            pytest.param(DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "expert-grid-emma.xlsx", id="expert-grid-emma"),
        ],
    )
    def test_excel_importer_valid_domain_expert(self, filepath: Path):
        domain_rules = ExcelImporter(filepath).to_rules(errors="raise", role=RoleTypes.domain_expert)

        assert isinstance(domain_rules, DomainRules)

    def test_excel_importer_valid_information_architect(self):
        information_rules = ExcelImporter(
            DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "information-architect-david.xlsx"
        ).to_rules(
            errors="raise",
            role=RoleTypes.information_architect,
        )

        assert isinstance(information_rules, InformationRules)

    @pytest.mark.skip("This is not the intended behavior")
    def test_excel_importer_invalid_information_architect(self):
        expected_issues = IssueList(
            [
                SheetMissingError(["Classes"]),
            ]
        )

        _, issues = ExcelImporter(DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "expert-wind-energy-jon.xlsx").to_rules(
            errors="continue",
            role=RoleTypes.information_architect,
        )

        assert issues == expected_issues
