from cognite.client.data_classes.data_modeling import InstanceApply

from cognite.neat._graph.extractors import AssetsExtractor, RdfFileExtractor
from cognite.neat._graph.loaders import DMSLoader
from cognite.neat._rules.catalog import imf_attributes
from cognite.neat._rules.importers import ExcelImporter, InferenceImporter
from cognite.neat._rules.models.entities._single_value import ClassEntity, ViewEntity
from cognite.neat._rules.transformers import InformationToDMS
from cognite.neat._store import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA, IMF_EXAMPLE


def test_metadata_as_json_filed():
    store = NeatGraphStore.from_memory_store()
    store.write(
        AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml", unpack_metadata=False, as_write=True)
    )

    importer = InferenceImporter.from_graph_store(store)

    info_rules = ImporterPipeline.verify(importer)
    dms_rules = InformationToDMS().transform(info_rules).rules

    # simulating update of the DMS rules
    dms_rules.views[0].view = ViewEntity.load("neat_space:MyAsset(version=inferred)")

    for prop in dms_rules.properties:
        prop.view = ViewEntity.load("neat_space:MyAsset(version=inferred)")
        prop.view_property = f"my_{prop.view_property}"

    # simulating update of the INFORMATION rules

    info_rules.classes[0].class_ = ClassEntity.load("neat_space:YourAsset")
    for prop in info_rules.properties:
        prop.class_ = ClassEntity.load("neat_space:YourAsset")
        prop.property_ = f"your_{prop.property_}"

    store.add_rules(info_rules)

    loader = DMSLoader.from_rules(dms_rules, store, dms_rules.metadata.space)
    instances = {instance.external_id: instance for instance in loader._load() if isinstance(instance, InstanceApply)}

    # metadata not unpacked but kept as Json obj
    assert isinstance(
        instances["Asset_4288662884680989"].sources[0].properties["my_metadata"],
        dict,
    )

    assert instances["Asset_4288662884680989"].type.external_id == "MyAsset"
    assert instances["Asset_4288662884680989"].type.space == "neat_space"


def test_imf_attribute_nodes():
    # this test also accounts for renaming of classes
    # as well omitting to remove namespace from values if
    # properties are not specified to be object properties

    info_rules = ImporterPipeline.verify(ExcelImporter(imf_attributes))

    dms_rules = InformationToDMS().transform(info_rules).rules

    store = NeatGraphStore.from_oxi_store(rules=info_rules)
    store.write(RdfFileExtractor(IMF_EXAMPLE))

    loader = DMSLoader.from_rules(dms_rules, store, instance_space="knowledge")
    knowledge_nodes = list(loader.load())

    assert len(knowledge_nodes) == 56
    assert knowledge_nodes[0].sources[0].properties["predicate"].startswith("http")
    assert len(store.multi_type_instances) == 63
