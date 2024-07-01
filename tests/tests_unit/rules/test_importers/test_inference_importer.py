from cognite.neat.graph.examples import nordic44_knowledge_graph
from cognite.neat.rules.importers import InferenceImporter
from cognite.neat.rules.models.entities import MultiValueTypeInfo


def test_rdf_inference():
    rules, _ = InferenceImporter.from_rdf_file(nordic44_knowledge_graph).to_rules(
        errors="continue"
    )

    assert len(rules.properties) == 312
    assert len(rules.classes) == 59

    # checking multi-value type
    assert set(rules.properties.data[19].value_type.types) == set(
        MultiValueTypeInfo.load(
            "inferred:ConformLoad | inferred:NonConformLoad | "
            "inferred:GeneratingUnit | inferred:ACLineSegment | inferred:PowerTransformer"
        ).types
    )

    # we should have 4 multi-value property
    assert (
        len(
            [
                prop_
                for prop_ in rules.properties
                if isinstance(prop_.value_type, MultiValueTypeInfo)
            ]
        )
        == 4
    )
