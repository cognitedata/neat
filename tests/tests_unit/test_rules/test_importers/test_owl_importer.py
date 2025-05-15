from cognite.neat.core._data_model import importers
from cognite.neat.core._data_model._constants import EntityTypes
from cognite.neat.core._data_model.analysis import DataModelAnalysis
from cognite.neat.core._data_model.models.entities import ConceptEntity
from cognite.neat.core._data_model.transformers._verification import VerifyAnyDataModel
from cognite.neat.core._issues import catch_issues


def test_ill_formed_owl_importer():
    input = importers.OWLImporter.from_file(filepath="https://data.nobelprize.org/terms.rdf").to_data_model()
    with catch_issues() as issues:
        _ = VerifyAnyDataModel().transform(input)

    assert len(issues) == 6
    assert issues.has_errors
    assert issues.has_errors
    assert str(issues.errors[0].identifier) == "neat_space:Award"

    acceptable_properties = []

    for prop in input.unverified_data_model.properties:
        if prop.concept != "Award":
            acceptable_properties.append(prop)

    input.unverified_data_model.properties = acceptable_properties

    with catch_issues():
        rules = VerifyAnyDataModel().transform(input)

    assert len(rules.concepts) == 4
    assert len(rules.properties) == 9

    # this is rdf:PlainLiteral edge case
    assert (
        DataModelAnalysis(rules)
        .properties_by_id_by_concept()[ConceptEntity.load("neat_space:LaureateAward")]["motivation"]
        .type_
        == EntityTypes.data_property
    )
