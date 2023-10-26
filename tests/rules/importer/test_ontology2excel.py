from cognite.neat.rules import importer
from cognite.neat.rules.models.tables import Tables
from tests import config


def test_owl2transformation_rules() -> None:
    # Arrange
    owl_importer = importer.OWLImporter(config.WIND_ONTOLOGY)

    # Act
    tables = owl_importer.to_tables()

    # Assert
    assert str(tables[Tables.metadata].iloc[0, 1]) == "https://kg.cognite.ai/wind/"
    assert len(set(tables[Tables.classes].Class.values)) == 68
