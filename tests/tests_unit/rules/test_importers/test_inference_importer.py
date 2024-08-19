from cognite.neat.graph.examples import nordic44_knowledge_graph
from cognite.neat.graph.extractors import AssetsExtractor, RdfFileExtractor
from cognite.neat.rules.importers import InferenceImporter
from cognite.neat.rules.models.data_types import Json
from cognite.neat.rules.models.entities import MultiValueTypeInfo
from cognite.neat.stores import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_rdf_inference():
    store = NeatGraphStore.from_oxi_store()
    extractor = RdfFileExtractor(nordic44_knowledge_graph, base_uri="http://nordic44.com/")
    store.write(extractor)

    rules = InferenceImporter.from_graph_store(store).to_rules(errors="raise")

    assert len(rules.properties) == 312
    assert len(rules.classes) == 59

    # checking multi-value type
    multi_value_property = "OperatingShare.PowerSystemResource"
    prop = next((prop for prop in rules.properties if prop.property_ == multi_value_property), None)
    assert prop is not None, f"Failed to infer expected multi-value property {multi_value_property}"
    assert set(prop.value_type.types) == set(
        MultiValueTypeInfo.load(
            "inferred:ConformLoad | inferred:NonConformLoad | "
            "inferred:GeneratingUnit | inferred:ACLineSegment | inferred:PowerTransformer"
        ).types
    )

    # we should have 4 multi-value property
    assert len([prop_ for prop_ in rules.properties if isinstance(prop_.value_type, MultiValueTypeInfo)]) == 4


def test_json_value_type_inference():
    store = NeatGraphStore.from_memory_store()

    extractor = AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml", unpack_metadata=False)

    store.write(extractor)

    rules, _ = InferenceImporter.from_graph_store(store, check_for_json_string=True).to_rules(errors="continue")

    properties = {prop.property_: prop for prop in rules.properties}

    assert len(rules.properties) == 5
    assert len(rules.classes) == 1

    assert isinstance(properties["metadata"].value_type, Json)
