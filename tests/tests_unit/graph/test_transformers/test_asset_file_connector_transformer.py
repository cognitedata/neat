import pytest

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph import extractors, transformers
from cognite.neat.stores import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_asset_file_connector_transformer():
    store = NeatGraphStore.from_memory_store()

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml"))

    # Extract time series
    store.write(extractors.FilesExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "files.yaml"))

    # Connect assets and time series
    store.transform(transformers.AssetFileConnector())

    result = list(store.graph.query(f"SELECT ?asset ?file WHERE {{ ?asset <{DEFAULT_NAMESPACE.file}> ?file}}"))

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
    store = NeatGraphStore.from_memory_store()

    with pytest.warns(
        UserWarning,
        match="Cannot transform graph store with AssetFileConnector, missing one or more required change",
    ):
        store.transform(transformers.AssetFileConnector())

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml"))

    # Extract time series
    store.write(extractors.FilesExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "files.yaml"))

    # Connect assets and time series
    store.transform(transformers.AssetFileConnector())

    with pytest.warns(UserWarning, match="Cannot transform graph store with AssetFileConnector, already applied"):
        store.transform(transformers.AssetFileConnector())
