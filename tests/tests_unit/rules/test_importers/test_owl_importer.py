from cognite.neat.rules import importers
from cognite.neat.rules._analysis._information_rules import InformationArchitectRulesAnalysis
from cognite.neat.rules.models._rules._types import ClassEntity, EntityTypes


def test_owl_importer():
    rules, _ = importers.OWLImporter(
        owl_filepath="https://data.nobelprize.org/terms.rdf", make_compliant=True
    ).to_rules()

    assert len(rules.classes) == 11
    assert len(rules.properties) == 16

    # this is rdf:PlainLiteral edge case
    assert (
        InformationArchitectRulesAnalysis(rules)
        .class_property_pairs()[ClassEntity.from_raw("neat:LaureateAward")]["motivation"]
        .type_
        == EntityTypes.data_property
    )
