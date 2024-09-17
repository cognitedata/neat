from cognite.neat.graph.extractors import AssetsExtractor, RdfFileExtractor
from cognite.neat.graph.loaders import DMSLoader
from cognite.neat.rules.examples import imf_info_rules
from cognite.neat.rules.importers import ExcelImporter, InferenceImporter
from cognite.neat.rules.transformers import ImporterPipeline, InformationToDMS
from cognite.neat.store import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA, IMF_EXAMPLE


def test_metadata_as_json_filed():
    store = NeatGraphStore.from_memory_store()
    store.write(AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml", unpack_metadata=False))

    importer = InferenceImporter.from_graph_store(store, prefix="some-prefix")

    rules = ImporterPipeline.verify(importer)
    store.add_rules(rules)

    dms_rules = InformationToDMS().transform(rules).rules

    loader = DMSLoader.from_rules(dms_rules, store, dms_rules.metadata.space)
    instances = {instance.external_id: instance for instance in loader._load()}

    # metadata not unpacked but kept as Json obj
    assert isinstance(instances["Asset_4288662884680989"].sources[0].properties["metadata"], dict)


def test_imf_attribute_nodes():
    # this test also accounts for renaming of classes
    # as well omitting to remove namespace from values if
    # properties are not specified to be object properties

    info_rules = ImporterPipeline.verify(ExcelImporter(imf_info_rules))
    dms_rules = InformationToDMS().transform(info_rules).rules

    store = NeatGraphStore.from_oxi_store(rules=info_rules)
    store.write(RdfFileExtractor(IMF_EXAMPLE, mime_type="text/turtle"))

    loader = DMSLoader.from_rules(dms_rules, store, instance_space="knowledge")
    knowledge_nodes = list(loader.load())

    assert len(knowledge_nodes) == 56
    assert knowledge_nodes[0].sources[0].properties["predicate"].startswith("http://")
