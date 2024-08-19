import pytest

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph import extractors, transformers
from cognite.neat.stores import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_asset_sequence_connector_transformer():
    store = NeatGraphStore.from_memory_store()

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml"))

    # Extract time series
    store.write(extractors.SequencesExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "sequences.yaml"))

    # Connect assets and time series
    store.transform(transformers.AssetSequenceConnector())

    result = list(
        store.graph.query(f"SELECT ?asset ?sequence WHERE {{ ?asset <{DEFAULT_NAMESPACE.sequence}> ?sequence}}")
    )

    assert len(result) == 2
    assert result[0][0] == result[1][0]
    assert result[0][0] == DEFAULT_NAMESPACE.Asset_78504378486679
    assert result[0][1] != result[1][1]
    assert {res[1] for res in result} == {
        DEFAULT_NAMESPACE.Sequence_82080677975658,
        DEFAULT_NAMESPACE.Sequence_85080677975658,
    }


def test_asset_sequence_connector_transformer_warning():
    store = NeatGraphStore.from_memory_store()

    with pytest.warns(
        UserWarning,
        match="Cannot transform graph store with AssetSequenceConnector, missing one or more required change",
    ):
        store.transform(transformers.AssetSequenceConnector())

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml"))

    # Extract time series
    store.write(extractors.SequencesExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "sequences.yaml"))

    # Connect assets and time series
    store.transform(transformers.AssetSequenceConnector())

    with pytest.warns(UserWarning, match="Cannot transform graph store with AssetSequenceConnector, already applied"):
        store.transform(transformers.AssetSequenceConnector())
