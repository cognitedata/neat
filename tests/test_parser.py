import pandas as pd
import pytest
from pydantic import ValidationError

from cognite.neat.core import rules
from cognite.neat.core.rules._loader import excel_file_to_table_by_name
from cognite.neat.core.rules._parser import Tables, from_tables
from tests import config


@pytest.fixture(scope="session")
def raw_transformation_tables() -> dict[str, pd.DataFrame]:
    return excel_file_to_table_by_name(config.TNT_TRANSFORMATION_RULES)


def test_parse_transformation_rules(raw_transformation_tables):
    assert from_tables(raw_transformation_tables)


def generate_parse_transformation_invalid_rules_test_data():
    raw_tables = excel_file_to_table_by_name(config.TNT_TRANSFORMATION_RULES)

    invalid_class_label = raw_tables
    invalid_class_label[Tables.properties] = invalid_class_label[Tables.properties].copy()
    invalid_class_label[Tables.properties].loc[0, "Class"] = "non existing class"
    yield pytest.param(invalid_class_label, id="Invalid mapping rule")


@pytest.mark.parametrize("raw_tables", generate_parse_transformation_invalid_rules_test_data())
def test_parse_transformation_invalid_rules(raw_tables: dict[str, pd.DataFrame]):
    with pytest.raises(ValidationError):
        rules.parse_transformation_rules(raw_tables)
