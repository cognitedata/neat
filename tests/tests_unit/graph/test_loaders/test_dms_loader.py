from cognite.neat.graph.extractors import AssetsExtractor
from cognite.neat.graph.loaders import DMSLoader
from cognite.neat.rules.importers import InferenceImporter
from cognite.neat.rules.transformers import InformationToDMS
from cognite.neat.store import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_metadata_as_json_filed():
    store = NeatGraphStore.from_memory_store()
    store.write(AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml", unpack_metadata=False))

    importer = InferenceImporter.from_graph_store(store, check_for_json_string=True, prefix="some-prefix")

    rules, _ = importer.to_rules()
    store.add_rules(rules)

    dms_rules = InformationToDMS().transform(rules).rules

    loader = DMSLoader.from_rules(dms_rules, store, dms_rules.metadata.space)
    instances = {instance.external_id: instance for instance in loader._load()}

    # metadata not unpacked but kept as Json obj
    assert isinstance(instances["Asset_4288662884680989"].sources[0].properties["metadata"], dict)
