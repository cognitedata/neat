from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._instances import extractors, transformers
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._store import NeatInstanceStore
from tests.v0.data import InstanceData


def test_asset_depth_transformer_without_typing():
    store = NeatInstanceStore.from_memory_store()
    store.write(extractors.AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml))

    transformer = transformers.AddAssetDepth()

    store.transform(transformer)

    result = list(store.dataset.query(f"SELECT ?s WHERE {{ ?s <{DEFAULT_NAMESPACE.depth}> 0}}"))

    assert len(result) == 1
    assert result[0][0] == DEFAULT_NAMESPACE.Asset_4901062138807933
    assert set(store.dataset.query(f"SELECT ?s WHERE {{ ?s <{DEFAULT_NAMESPACE.depth}> ?d}}")) == set(
        store.dataset.query(f"SELECT ?s WHERE {{ ?s a <{DEFAULT_NAMESPACE.Asset}>}}")
    )


def test_asset_depth_transformer_with_typing():
    store = NeatInstanceStore.from_memory_store()
    extractor = extractors.AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml)
    store.write(extractor)

    transformer = transformers.AddAssetDepth(
        depth_typing={
            0: "RootCimNode",
            1: "GeographicalRegion",
            2: "SubGeographicalRegion",
            3: "Substation",
        }
    )

    store.transform(transformer)

    assert set(store.queries.select.summarize_instances()) == {
        ("GeographicalRegion", 1),
        ("RootCimNode", 1),
        ("SubGeographicalRegion", 1),
        ("Substation", 1),
    }


def test_asset_depth_transformer_warning():
    store = NeatInstanceStore.from_memory_store()

    transformer = transformers.AddAssetDepth()
    issues1 = store.transform(transformer)
    assert len(issues1) == 1
    assert issues1[0] == NeatValueError(
        "Cannot transform graph store with AddAssetDepth, missing one or more required changes AssetsExtractor"
    )

    extractor = extractors.AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml)
    store.write(extractor)
    _ = store.transform(transformer)

    issues2 = store.transform(transformer)
    assert len(issues2) == 1
    assert issues2[0] == NeatValueError("Cannot transform graph store with AddAssetDepth, already applied")
