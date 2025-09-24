import urllib.parse

from cognite.client.data_classes.data_modeling import InstanceApply
from rdflib import RDF, Literal, Namespace

from cognite.neat import NeatSession
from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._data_model.analysis import DataModelAnalysis
from cognite.neat.v0.core._data_model.importers import InferenceImporter
from cognite.neat.v0.core._data_model.models.data_types import DataType, Integer, Json, Long
from cognite.neat.v0.core._data_model.models.entities import MultiValueTypeInfo
from cognite.neat.v0.core._data_model.models.entities._single_value import UnknownEntity
from cognite.neat.v0.core._data_model.transformers import VerifyAnyDataModel
from cognite.neat.v0.core._instances.examples import nordic44_knowledge_graph
from cognite.neat.v0.core._instances.extractors import AssetsExtractor, RdfFileExtractor
from cognite.neat.v0.core._instances.loaders import DMSLoader, InstanceSpaceLoader
from cognite.neat.v0.core._issues import catch_issues
from cognite.neat.v0.core._store import NeatInstanceStore
from tests.v0.data import GraphData, InstanceData


def test_rdf_inference():
    store = NeatInstanceStore.from_oxi_local_store()
    extractor = RdfFileExtractor(nordic44_knowledge_graph, base_uri="http://nordic44.com/")
    store.write(extractor)

    with catch_issues():
        importer = InferenceImporter.from_graph_store(store, ("inferred", "nordic44_data_model", "rdf"))
        rules = VerifyAnyDataModel().transform(importer.to_data_model())

    assert len(rules.properties) == 332
    assert len(rules.concepts) == 59

    # checking multi-value type

    prop = next(
        (
            prop
            for prop in rules.properties
            if prop.property_ == "OperatingShare.PowerSystemResource" and prop.concept.suffix == "OperatingShare"
        ),
        None,
    )

    assert prop is not None, "Failed to infer expected multi-value property OperatingShare.PowerSystemResource"
    assert set(prop.value_type.types) == set(
        MultiValueTypeInfo.load(
            "inferred:ConformLoad, inferred:NonConformLoad, "
            "inferred:GeneratingUnit, inferred:ACLineSegment, inferred:PowerTransformer"
        ).types
    )

    # we should have 4 multi-value property
    assert len(DataModelAnalysis(rules).multi_value_properties) == 4


def test_rdf_inference_with_removal_of_unknown_type():
    EX = Namespace("http://example.org/")
    SUBSTATION = Namespace("http://example.org/substation/")
    TERMINAL = Namespace("http://example.org/terminal/")
    store = NeatInstanceStore.from_oxi_local_store()

    store.dataset.add((EX.substation1, RDF.type, SUBSTATION.Substation))
    store.dataset.add((EX.substation2, RDF.type, SUBSTATION.Substation))
    store.dataset.add((EX.substation3, RDF.type, SUBSTATION.Substation))
    store.dataset.add((EX.terminal1, RDF.type, TERMINAL.Terminal))
    store.dataset.add((EX.terminal2, RDF.type, TERMINAL.Terminal))
    store.dataset.add((EX.substation1, EX.hasTerminal, EX.terminal1))
    store.dataset.add((EX.substation2, EX.hasTerminal, EX.terminal3))
    store.dataset.add((EX.substation1, EX.name, Literal("Substation 1")))
    store.dataset.add((EX.substation3, EX.name, Literal("Substation 3")))

    with catch_issues():
        importer = InferenceImporter.from_graph_store(store, ("inferred", "drop_unknown", "rdf"))
        rules = VerifyAnyDataModel().transform(importer.to_data_model())

    for prop in rules.properties:
        assert not isinstance(prop.value_type, MultiValueTypeInfo)


def test_rdf_inference_with_none_existing_node():
    store = NeatInstanceStore.from_oxi_local_store()
    extractor = RdfFileExtractor(GraphData.low_quality_graph_ttl)
    store.write(extractor)

    with catch_issues():
        importer = InferenceImporter.from_graph_store(store, non_existing_node_type=UnknownEntity())
        rules = VerifyAnyDataModel().transform(importer.to_data_model())

    assert len(rules.properties) == 14
    assert len(rules.concepts) == 6

    assert {prop.property_: prop.value_type for prop in rules.properties}[
        "Location.CoordinateSystem"
    ] == UnknownEntity()


def test_json_value_type_inference():
    store = NeatInstanceStore.from_memory_store()

    extractor = AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml, unpack_metadata=False)

    store.write(extractor)

    with catch_issues():
        importer = InferenceImporter.from_graph_store(store)
        rules = VerifyAnyDataModel().transform(importer.to_data_model())

    properties = {prop.property_: prop for prop in rules.properties}

    assert len(rules.properties) == 9
    assert len(rules.concepts) == 1

    assert isinstance(properties["metadata"].value_type, Json)


def test_integer_as_long():
    store = NeatInstanceStore.from_memory_store()
    for triple in GraphData.car.TRIPLES:
        store.dataset.add(triple)

    with catch_issues():
        importer = InferenceImporter.from_graph_store(store)
        rules = VerifyAnyDataModel().transform(importer.to_data_model())

    data_types = {prop.value_type for prop in rules.properties if isinstance(prop.value_type, DataType)}

    assert Integer() not in data_types
    assert Long() in data_types


def test_infer_with_bad_property_names() -> None:
    neat = NeatSession()
    neat._state.instances.store._add_triples(
        [
            (DEFAULT_NAMESPACE["MyAsset"], RDF.type, DEFAULT_NAMESPACE["Asset"]),
            (
                DEFAULT_NAMESPACE["MyAsset"],
                DEFAULT_NAMESPACE[urllib.parse.quote("My Property ill-formed")],
                Literal("My Value"),
            ),
        ],
        named_graph=neat._state.instances.store.default_named_graph,
    )
    neat.infer()
    assert neat._state.data_model_store.provenance
    info = neat._state.data_model_store.last_verified_conceptual_data_model

    assert info is not None
    assert len(info.properties) == 1
    assert info.properties[0].property_ == "myPropertyIllFormed"


def test_infer_importer_names_different_casing() -> None:
    neat = NeatSession()
    neat._state.instances.store._add_triples(
        [
            (DEFAULT_NAMESPACE["MyAsset"], RDF.type, DEFAULT_NAMESPACE["Asset"]),
            (DEFAULT_NAMESPACE["MyAsset"], DEFAULT_NAMESPACE["deleteFlag"], Literal(True)),
            (DEFAULT_NAMESPACE["MyAsset2"], RDF.type, DEFAULT_NAMESPACE["Asset"]),
            (DEFAULT_NAMESPACE["MyAsset2"], DEFAULT_NAMESPACE["DeleteFlag"], Literal(False)),
        ],
        named_graph=neat._state.instances.store.default_named_graph,
    )
    neat.infer()
    assert neat._state.data_model_store.provenance
    info = neat._state.data_model_store.last_verified_conceptual_data_model

    assert info is not None
    assert len(info.properties) == 1
    assert info.properties[0].instance_source is not None
    assert len(info.properties[0].instance_source) == 2

    neat.convert()

    dms_rules = neat._state.data_model_store.last_verified_physical_data_model
    info_rules = neat._state.data_model_store.last_verified_conceptual_data_model

    store = neat._state.instances.store
    instances = [
        instance
        for instance in DMSLoader(
            dms_rules, info_rules, store, InstanceSpaceLoader(instance_space="sp_instance_space").space_by_instance_uri
        ).load()
        if isinstance(instance, InstanceApply)
    ]
    actual = {node.external_id: node.sources[0].properties for node in instances}
    assert actual == {
        "MyAsset": {"DeleteFlag": True},
        "MyAsset2": {"DeleteFlag": False},
    }
