import pandas as pd
import pytest
from pydantic import ValidationError

from cognite.neat.rules.importer._base import Tables
from cognite.neat.rules.importer.spreadsheet2rules import ExcelImporter
from cognite.neat.rules.models.raw_rules import RawRules
from tests import config


@pytest.fixture(scope="session")
def raw_transformation_tables() -> dict[str, pd.DataFrame]:
    return RawRules.from_excel(config.TNT_TRANSFORMATION_RULES)


def test_parse_transformation_rules(raw_transformation_tables):
    assert raw_transformation_tables.to_transformation_rules()


def generate_parse_transformation_invalid_rules_test_data():
    raw_tables = ExcelImporter(config.TNT_TRANSFORMATION_RULES).to_raw_dataframe()

    invalid_class_label = raw_tables
    invalid_class_label[Tables.properties] = invalid_class_label[Tables.properties].copy()
    invalid_class_label[Tables.properties].loc[0, "Class"] = "non existing class"
    yield pytest.param(invalid_class_label, id="Invalid mapping rule")


@pytest.mark.parametrize("raw_tables", generate_parse_transformation_invalid_rules_test_data())
def test_parse_transformation_invalid_rules(raw_tables: dict[str, pd.DataFrame]):
    with pytest.raises(ValidationError):
        RawRules.from_tables(raw_tables).validate()
