from cognite.neat.rules import importers
from cognite.neat.rules._constants import EntityTypes
from cognite.neat.rules.analysis import InformationAnalysis
from cognite.neat.rules.models.entities import ClassEntity
from cognite.neat.rules.transformers import ImporterPipeline
from tests.config import IMF_EXAMPLE


def test_imf_importer():
    rules = ImporterPipeline.verify(importers.IMFImporter.from_file(IMF_EXAMPLE, "imf"))

    assert len(rules.classes) == 69
    assert len(rules.properties) == 156

    # this is rdf:PlainLiteral edge case
    class_property_pairs = InformationAnalysis(rules).class_property_pairs()

    assert (
        class_property_pairs[ClassEntity.load("pcaimf:IMF_1ccc23fc_42ca_4b8a_acd5_ef2beddf7f12")]["hasTerminal"].type_
        == EntityTypes.object_property
    )

    assert (
        str(
            class_property_pairs[ClassEntity.load("pcaimf:IMF_1ccc23fc_42ca_4b8a_acd5_ef2beddf7f12")][
                "hasTerminal"
            ].transformation
        )
        == "prefix-3:1ccc23fc-42ca-4b8a-acd5-ef2beddf7f12(prefix-6:hasTerminal)"
    )
