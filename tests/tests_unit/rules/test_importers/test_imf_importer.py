from cognite.neat.rules import importers
from cognite.neat.rules.analysis import InformationAnalysis
from cognite.neat.rules.models.entities import ClassEntity, EntityTypes
from cognite.neat.rules.transformers import ImporterPipeline
from tests.config import IMF_EXAMPLE


def test_imf_importer():
    rules = ImporterPipeline.verify(importers.IMFImporter(filepath=IMF_EXAMPLE))

    assert len(rules.classes) == 69
    assert len(rules.properties) == 156

    # this is rdf:PlainLiteral edge case
    assert (
        InformationAnalysis(rules)
        .class_property_pairs()[ClassEntity.load("pcaimf:IMF_1ccc23fc_42ca_4b8a_acd5_ef2beddf7f12")]["hasTerminal"]
        .type_
        == EntityTypes.object_property
    )
