from cognite.neat.graph.examples import nordic44_knowledge_graph
from cognite.neat.rules.importers import InferenceImporter


def test_rdf_inference():
    rules, _ = InferenceImporter.from_rdf_file(nordic44_knowledge_graph, max_number_of_instance=1).to_rules(
        errors="continue"
    )

    assert len(rules.properties) == 296
    assert len(rules.classes) == 59
