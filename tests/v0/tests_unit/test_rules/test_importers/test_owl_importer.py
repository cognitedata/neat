from cognite.neat.v0.core._data_model import importers
from cognite.neat.v0.core._data_model._constants import EntityTypes
from cognite.neat.v0.core._data_model.analysis import DataModelAnalysis
from cognite.neat.v0.core._data_model.models.entities import ConceptEntity
from cognite.neat.v0.core._data_model.transformers._verification import VerifyAnyDataModel
from cognite.neat.v0.core._issues import catch_issues
from cognite.neat.v0.core._issues.warnings._models import DanglingPropertyWarning, UndefinedConceptWarning
from cognite.neat.v0.core._issues.warnings._resources import ResourceRegexViolationWarning
from tests.v0.data import SchemaData


def test_ill_formed_owl_importer():
    input = importers.OWLImporter.from_file(filepath="https://data.nobelprize.org/terms.rdf").to_data_model()
    with catch_issues() as issues:
        _ = VerifyAnyDataModel().transform(input)

    assert len(issues) == 7
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

    # quoting is successful, but regex warnings are raised
    assert not issues.has_errors
    assert issues.has_warnings
    assert issues.has_warning_type(UndefinedConceptWarning)
    assert issues.has_warning_type(ResourceRegexViolationWarning)
    assert issues.has_warning_type(DanglingPropertyWarning)

    expected_concepts = {
        ConceptEntity(
            prefix="neat_space", suffix="Control.Panel-1%28Safety%29~%3F%40%21%24%26%27%2A%2B%2C%3B%3D%25%5B%5D"
        ),
        ConceptEntity(prefix="neat_space", suffix="Machine.Type-A%2801%29~%3F%40%21%24%26%27%2A%2B%2C%3B%3D%25%5B%5D"),
        ConceptEntity(
            prefix="neat_space", suffix="Sensor.Unit_01%28Temp%29~%3F%40%21%24%26%27%2A%2B%2C%3B%3D%25%5B%5D"
        ),
        ConceptEntity(prefix="neat_space", suffix="Sensor"),
    }

    expected_properties = {
        "contains.Serial-Number%28ID%29%3AX~%3F%40%21%24%26%27%2A%2B%2C%3B%3D%25%5B%5D",
        "has.Relation-Type%28Generic%29%3AX~%3F%40%21%24%26%27%2A%2B%2C%3B%3D%25%5B%5D",
        "has.Sensor-Unit%2801%29%3ATemp~%3F%40%21%24%26%27%2A%2B%2C%3B%3D%25%5B%5D",
        "has.Value-Reading%28Temp%29%3AC~%3F%40%21%24%26%27%2A%2B%2C%3B%3D%25%5B%5D",
        "is.Connected-To%28Control%29%3APanel~%3F%40%21%24%26%27%2A%2B%2C%3B%3D%25%5B%5D",
        "is.Controlled-By%28Panel%29%3ASafety~%3F%40%21%24%26%27%2A%2B%2C%3B%3D%25%5B%5D",
        "links.Interface-Module%2802%29%3AIO~%3F%40%21%24%26%27%2A%2B%2C%3B%3D%25%5B%5D",
        "logs.Data-Stream%2801%29%3ARaw~%3F%40%21%24%26%27%2A%2B%2C%3B%3D%25%5B%5D",
        "reports.Status-Flag%28OK%29%3A1~%3F%40%21%24%26%27%2A%2B%2C%3B%3D%25%5B%5D",
        "multiConnect",
    }

    actual_concepts = {concept.concept: concept for concept in conceptual_data_model.concepts}
    actual_properties = {prop.property_ for prop in conceptual_data_model.properties}
    assert set(actual_concepts) == expected_concepts
    assert actual_properties == expected_properties
    assert actual_concepts[ConceptEntity(prefix="neat_space", suffix="Sensor")].implements == [
        ConceptEntity(prefix="cdf_cdm", suffix="CogniteAsset", version="v1")
    ]
