from rdflib import URIRef

from cognite.neat.graph.examples import nordic44_knowledge_graph
from cognite.neat.graph.extractors import RdfFileExtractor
from cognite.neat.graph.issues.loader import InvalidInstanceError
from cognite.neat.graph.loaders import AssetLoader
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.rules.importers import ExcelImporter
from tests import config


def test_generation_of_assets():
    store = NeatGraphStore.from_memory_store()
    store.write(RdfFileExtractor(nordic44_knowledge_graph, base_uri=URIRef("http://purl.org/nordic44#")))

    asset_rules, _ = ExcelImporter(filepath=config.DATA_FOLDER / "asset-architect-test.xlsx").to_rules()
    store.add_rules(asset_rules.as_information_rules())

    loader = AssetLoader(store, asset_rules, 1983)
    result = list(loader._load())

    assets = []
    errors = []
    for r in result:
        if not isinstance(r, InvalidInstanceError):
            assets.append(r)
        else:
            errors.append(r)

    assert len(assets) == 450
    assert len(errors) == 88
