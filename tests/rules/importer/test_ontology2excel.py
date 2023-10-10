import pytest

from cognite.neat.rules import importer
from cognite.neat.rules.importer import owl2excel
from cognite.neat.rules.parser import RawTables, read_excel_file_to_table_by_name
from tests import config


@pytest.fixture(scope="function")
def owl_based_rules() -> RawTables:
    owl2excel(config.WIND_ONTOLOGY)

    return RawTables(**read_excel_file_to_table_by_name(config.WIND_ONTOLOGY.parent / "transformation_rules.xlsx"))


def test_owl2transformation_rules(owl_based_rules: RawTables) -> None:
    # Arrange
    owl_importer = importer.OWLImporter(config.WIND_ONTOLOGY)

    # Act
    owl_importer.to_tables()

    # Assert
    assert owl_based_rules.Metadata.iloc[0, 1] == "https://kg.cognite.ai/wind/"
    assert len(set(owl_based_rules.Classes.Class.values)) == 68
