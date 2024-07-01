import pytest

from cognite.neat.legacy.rules import importers
from cognite.neat.legacy.rules.models.rules import Rules
from tests import config as config


@pytest.fixture(scope="session")
def transformation_rules() -> Rules:
    return importers.ExcelImporter(config.SIMPLECIM_TRANSFORMATION_RULES).to_rules()
