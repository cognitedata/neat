import sys

import pandas as pd
import pytest
from pydantic import ValidationError

from cognite.neat.rules import importer
from cognite.neat.rules._importer._spreadsheet2rules import ExcelImporter
from cognite.neat.rules.models import Tables
from cognite.neat.rules.models._rules import RULES_PER_ROLE
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


def test_excel_importer_domain_expert():
    assert isinstance(
        ExcelImporter(DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "expert-wind-energy-jon.xlsx").to_rules(
            RoleTypes.domain_expert,
        ),
        RULES_PER_ROLE[RoleTypes.domain_expert],
    )

    assert isinstance(
        ExcelImporter(DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "expert-grid-emma.xlsx").to_rules(
            RoleTypes.domain_expert,
        ),
        RULES_PER_ROLE[RoleTypes.domain_expert],
    )


def test_excel_importer_information_architect():
    assert isinstance(
        ExcelImporter(DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "information-architect-david.xlsx").to_rules(
            RoleTypes.information_architect,
        ),
        RULES_PER_ROLE[RoleTypes.information_architect],
    )


def test_excel_importer_information_architect_invalid():
    with pytest.raises(ValueError) as e:
        ExcelImporter(DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "expert-wind-energy-jon.xlsx").to_rules(
            RoleTypes.information_architect,
        )

    assert str(e.value) == "Missing mandatory sheets: {'classes'}"
