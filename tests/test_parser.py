import pandas as pd
import pytest
from pydantic import ValidationError

from cognite.neat.core import parser, rules
from cognite.neat.core.configuration import Tables
from tests import config


def test_parse_transformation_rules(raw_transformation_tables):
    assert parser.parse_transformation_rules(raw_transformation_tables)


def generate_parse_transformation_invalid_rules_test_data():
    raw_tables = rules.loader.excel_file_to_table_by_name(config.TNT_TRANSFORMATION_RULES)

    invalid_class_label = raw_tables
    invalid_class_label[Tables.properties] = invalid_class_label[Tables.properties].copy()
    invalid_class_label[Tables.properties].loc[0, "Class"] = "non existing class"
    yield pytest.param(invalid_class_label, id="Invalid mapping rule")


@pytest.mark.parametrize("raw_tables", generate_parse_transformation_invalid_rules_test_data())
def test_parse_transformation_invalid_rules(raw_tables: dict[str, pd.DataFrame]):
    with pytest.raises(ValidationError):
        parser.parse_transformation_rules(raw_tables)
