from cognite.neat.core._data_model import importers
from cognite.neat.core._data_model._constants import EntityTypes
from cognite.neat.core._data_model.analysis import DataModelAnalysis
from cognite.neat.core._data_model.models.entities import ConceptEntity
from cognite.neat.core._data_model.transformers._verification import VerifyAnyDataModel
from cognite.neat.core._issues import catch_issues
from cognite.neat.core._issues.warnings._resources import ResourceNotDefinedWarning, ResourceRegexViolationWarning
from tests.data import SchemaData


def test_ill_formed_owl_importer():
    input = importers.OWLImporter.from_file(filepath="https://data.nobelprize.org/terms.rdf").to_data_model()
    with catch_issues() as issues:
        _ = VerifyAnyDataModel().transform(input)

    assert len(issues) == 6
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


def test_owl_enitity_quoting():
    input = importers.OWLImporter.from_file(filepath=SchemaData.Conceptual.ontology_with_regex_warnings).to_data_model()
    with catch_issues() as issues:
        conceptual_data_model = VerifyAnyDataModel().transform(input)

    categorized_issues = {}
    for issue in issues:
        if type(issue) not in categorized_issues:
            categorized_issues[type(issue)] = []
        categorized_issues[type(issue)].append(issue)

    assert len(issues) == 13
    # quoting is successful, but regex warnings are raised
    assert not issues.has_errors
    assert issues.has_warnings

    assert len(categorized_issues) == 2
    assert len(categorized_issues[ResourceRegexViolationWarning]) == 12
    assert len(categorized_issues[ResourceNotDefinedWarning]) == 1

    assert len(conceptual_data_model.concepts) == 3
    assert len(conceptual_data_model.properties) == 3
