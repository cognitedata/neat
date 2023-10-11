import pytest

from cognite.neat.rules import importer
from cognite.neat.rules.parser import RawTables
from tests import data


@pytest.mark.skipif(not data.CAPACITY_MARKET_JSON.exists(), reason="Requires data file")
def test_json2rules_importer() -> None:
    # Arrange
    json_importer = importer.JSONImporter(data.CAPACITY_MARKET_JSON)

    # Act
    tables = json_importer.to_tables()

    # Assert
    assert isinstance(tables, RawTables)
