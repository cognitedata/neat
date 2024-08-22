from cognite.neat.rules import importers
from cognite.neat.rules.analysis import InformationAnalysis
from cognite.neat.rules.models.entities import ClassEntity, EntityTypes
from tests.config import IMF_EXAMPLE


def test_imf_importer():
    rules, _ = importers.IMFImporter(filepath=IMF_EXAMPLE).to_rules()

    assert len(rules.classes) == 69
    assert len(rules.properties) == 156

    # this is rdf:PlainLiteral edge case
    assert (
        InformationAnalysis(rules)
        .class_property_pairs()[ClassEntity.load("pca-imf:IMF_1ccc23fc-42ca-4b8a-acd5-ef2beddf7f12")]["hasTerminal"]
        .type_
        == EntityTypes.object_property
    )
