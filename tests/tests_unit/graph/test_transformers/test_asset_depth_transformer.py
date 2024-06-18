from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph import extractors, transformers
from cognite.neat.graph.stores import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_asset_depth_transformer():
    store = NeatGraphStore.from_memory_store()
    extractor = extractors.AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml")
    store.write(extractor)

    transformer = transformers.AddAssetDepth()

    store.transform(transformer)

    result = list(store.graph.query(f"SELECT ?s WHERE {{ ?s <{DEFAULT_NAMESPACE.depth}> 1}}"))

    assert len(result) == 1
    assert result[0][0] == DEFAULT_NAMESPACE.Asset_78504378486679  #
