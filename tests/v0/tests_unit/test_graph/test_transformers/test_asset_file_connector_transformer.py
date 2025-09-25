from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._instances import extractors, transformers
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._store import NeatInstanceStore
from tests.v0.data import InstanceData


def test_asset_file_connector_transformer():
    store = NeatInstanceStore.from_memory_store()

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml))

    # Extract time series
    store.write(extractors.FilesExtractor.from_file(InstanceData.AssetCentricCDF.files_yaml))

    # Connect assets and time series
    store.transform(transformers.AssetFileConnector())

    result = list(store.dataset.query(f"SELECT ?asset ?file WHERE {{ ?asset <{DEFAULT_NAMESPACE.file}> ?file}}"))

    assert len(result) == 2
    assert result[0][0] != result[1][0]
    assert result[0][1] == result[1][1]
    assert {res[1] for res in result} == {
        DEFAULT_NAMESPACE.File_146805958863362,
    }
    assert {res[0] for res in result} == {
        DEFAULT_NAMESPACE.Asset_5132527530441957,
        DEFAULT_NAMESPACE.Asset_78504378486679,
    }


def test_asset_file_connector_transformer_warning():
    store = NeatInstanceStore.from_memory_store()

    issues1 = store.transform(transformers.AssetFileConnector())
    assert len(issues1) == 1
    assert issues1[0] == NeatValueError(
        "Cannot transform graph store with AssetFileConnector, missing one or more required changes "
        "AssetsExtractor and FilesExtractor"
    )

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml))

    # Extract time series
    store.write(extractors.FilesExtractor.from_file(InstanceData.AssetCentricCDF.files_yaml))

    # Connect assets and time series
    store.transform(transformers.AssetFileConnector())

    issues2 = store.transform(transformers.AssetFileConnector())
    assert len(issues2) == 1
    assert issues2[0] == NeatValueError("Cannot transform graph store with AssetFileConnector, already applied")
