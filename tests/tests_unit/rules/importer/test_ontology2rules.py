from cognite.neat.rules._importer._owl2rules import OWLImporter
from cognite.neat.rules.examples import wind_energy_ontology


def test_owl2transformation_rules() -> None:
    # Arrange
    owl_importer = OWLImporter(wind_energy_ontology)
    rules = owl_importer.to_rules(make_compliant=True)

    # Assert
    assert str(rules.metadata.namespace) == "https://kg.cognite.ai/wind/"
    assert len(rules.classes) == 71

