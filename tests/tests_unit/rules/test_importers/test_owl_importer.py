from cognite.neat.rules import importers
from cognite.neat.rules.analysis import InformationAnalysis
from cognite.neat.rules.models.entities import ClassEntity, EntityTypes


def test_owl_importer():
    rules, _ = importers.OWLImporter(filepath="https://data.nobelprize.org/terms.rdf").to_rules()

    assert len(rules.classes) == 11
    assert len(rules.properties) == 16

    # this is rdf:PlainLiteral edge case
    assert (
        InformationAnalysis(rules).class_property_pairs()[ClassEntity.load("neat:LaureateAward")]["motivation"].type_
        == EntityTypes.data_property
    )
