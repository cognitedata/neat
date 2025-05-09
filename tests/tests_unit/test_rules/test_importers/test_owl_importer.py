from cognite.neat.core._data_model import importers
from cognite.neat.core._data_model._constants import EntityTypes
from cognite.neat.core._data_model.analysis import RulesAnalysis
from cognite.neat.core._data_model.models.entities import ClassEntity
from cognite.neat.core._data_model.transformers._verification import VerifyAnyRules
from cognite.neat.core._issues import catch_issues


def test_ill_formed_owl_importer():
    input = importers.OWLImporter.from_file(filepath="https://data.nobelprize.org/terms.rdf").to_rules()
    with catch_issues() as issues:
        _ = VerifyAnyRules().transform(input)

    assert len(issues) == 6
    assert issues.has_errors
    assert issues.has_errors
    assert str(issues.errors[0].identifier) == "neat_space:Award"

    acceptable_properties = []

    for prop in input.rules.properties:
        if prop.class_ != "Award":
            acceptable_properties.append(prop)

    input.rules.properties = acceptable_properties

    with catch_issues():
        rules = VerifyAnyRules().transform(input)

    assert len(rules.classes) == 4
    assert len(rules.properties) == 9

    # this is rdf:PlainLiteral edge case
    assert (
        RulesAnalysis(rules)
        .properties_by_id_by_class()[ClassEntity.load("neat_space:LaureateAward")]["motivation"]
        .type_
        == EntityTypes.data_property
    )
