from cognite.neat._rules import importers
from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.analysis import InformationAnalysis
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._rules.transformers import ImporterPipeline


def test_owl_importer():
    rules = ImporterPipeline.verify(importers.OWLImporter.from_file(filepath="https://data.nobelprize.org/terms.rdf"))

    assert len(rules.classes) == 11
    assert len(rules.properties) == 16

    # this is rdf:PlainLiteral edge case
    assert (
        InformationAnalysis(rules).class_property_pairs()[ClassEntity.load("neat:LaureateAward")]["motivation"].type_
        == EntityTypes.data_property
    )
