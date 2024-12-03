from cognite.neat._rules import importers
from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.analysis import InformationAnalysis
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._rules.transformers._verification import VerifyAnyRules


def test_ill_formed_owl_importer():
    input = importers.OWLImporter.from_file(filepath="https://data.nobelprize.org/terms.rdf").to_rules()
    output = VerifyAnyRules("continue").try_transform(input)

    assert len(output.issues) == 6
    assert output.issues.has_errors
    assert output.issues.has_errors
    assert str(output.issues.errors[0].identifier) == "neat_space:Award"

    acceptable_properties = []

    for prop in input.rules.properties:
        if prop.class_ != "Award":
            acceptable_properties.append(prop)

    input.rules.properties = acceptable_properties

    output = VerifyAnyRules("continue").try_transform(input)

    assert len(output.rules.classes) == 4
    assert len(output.rules.properties) == 10

    # this is rdf:PlainLiteral edge case
    assert (
        InformationAnalysis(output.rules)
        .class_property_pairs()[ClassEntity.load("neat_space:LaureateAward")]["motivation"]
        .type_
        == EntityTypes.data_property
    )
