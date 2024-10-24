from cognite.neat._graph.examples import nordic44_knowledge_graph
from cognite.neat._graph.extractors import AssetsExtractor, RdfFileExtractor
from cognite.neat._rules.analysis import InformationAnalysis
from cognite.neat._rules.importers import InferenceImporter
from cognite.neat._rules.models.data_types import Json
from cognite.neat._rules.models.entities import MultiValueTypeInfo
from cognite.neat._rules.models.entities._single_value import UnknownEntity
from cognite.neat._rules.transformers import ImporterPipeline
from cognite.neat._store import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA, DATA_FOLDER


def test_rdf_inference():
    store = NeatGraphStore.from_oxi_store()
    extractor = RdfFileExtractor(nordic44_knowledge_graph, base_uri="http://nordic44.com/")
    store.write(extractor)

    rules = ImporterPipeline.verify(InferenceImporter.from_graph_store(store))

    assert len(rules.properties) == 332
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
    assert len(InformationAnalysis(rules).multi_value_properties) == 4


def test_rdf_inference_with_none_existing_node():
    store = NeatGraphStore.from_oxi_store()
    extractor = RdfFileExtractor(DATA_FOLDER / "low-quality-graph.ttl")
    store.write(extractor)

    rules = ImporterPipeline.verify(InferenceImporter.from_graph_store(store, non_existing_node_type=UnknownEntity()))

    assert len(rules.properties) == 14
    assert len(rules.classes) == 6

    assert {prop.property_: prop.value_type for prop in rules.properties}[
        "Location.CoordinateSystem"
    ] == UnknownEntity()


def test_json_value_type_inference():
    store = NeatGraphStore.from_memory_store()

    extractor = AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml", unpack_metadata=False)

    store.write(extractor)

    rules = ImporterPipeline.verify(InferenceImporter.from_graph_store(store))

    properties = {prop.property_: prop for prop in rules.properties}

    assert len(rules.properties) == 9
    assert len(rules.classes) == 1

    assert isinstance(properties["metadata"].value_type, Json)
