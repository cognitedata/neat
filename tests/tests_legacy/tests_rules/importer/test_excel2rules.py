import sys

import pandas as pd
import pytest
from pydantic import ValidationError

from cognite.neat.legacy.rules import importers
from cognite.neat.legacy.rules.models import Tables
from cognite.neat.legacy.rules.models.raw_rules import RawRules
from tests import config

if sys.version_info < (3, 11):
    pass


@pytest.fixture(scope="session")
def raw_rules() -> dict[str, pd.DataFrame]:
    return importers.ExcelImporter(config.SIMPLECIM_TRANSFORMATION_RULES).to_raw_rules()


def test_raw_rules_validation(raw_rules):
    assert raw_rules.to_rules()


def generate_invalid_raw_rules_test_data():
    raw_tables = importers.ExcelImporter(config.SIMPLECIM_TRANSFORMATION_RULES).to_tables()

    invalid_class_label = raw_tables
    invalid_class_label[Tables.properties] = invalid_class_label[Tables.properties].copy()
    invalid_class_label[Tables.properties].loc[0, "Class"] = "non existing class"
    yield pytest.param(invalid_class_label, id="Invalid mapping rule")


@pytest.mark.parametrize("raw_tables", generate_invalid_raw_rules_test_data())
def test_parse_transformation_invalid_rules(raw_tables: dict[str, pd.DataFrame]):
    with pytest.raises(ValidationError):
        RawRules.from_tables(raw_tables).to_rules()
