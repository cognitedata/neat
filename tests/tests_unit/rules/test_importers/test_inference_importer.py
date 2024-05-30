from cognite.neat.graph.examples import nordic44_knowledge_graph
from cognite.neat.rules.importers import InferenceImporter


def test_rdf_inference():
    rules, _ = InferenceImporter.from_rdf_file(nordic44_knowledge_graph, make_compliant=True).to_rules(
        errors="continue"
    )

    assert len(rules.properties) == 327
    assert len(rules.classes) == 59

    # make compliant will make sure that "." from the original property will be replace
    assert rules.properties.data[0].property_ == "CurrentLimit_value"

    # make compliant will do two things for this property:
    # 1. redefinition of property will get new ID by adding "_(property number)", in this case 20
    # 2. replace " " with "_"
    assert rules.properties.data[19].property_ == "Terminal_ConductingEquipment_20"
