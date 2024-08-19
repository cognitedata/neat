import pytest

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph import extractors, transformers
from cognite.neat.stores import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_asset_event_connector_transformer():
    store = NeatGraphStore.from_memory_store()

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml"))

    # Extract time series
    store.write(extractors.EventsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "events.yaml"))

    # Connect assets and time series
    store.transform(transformers.AssetEventConnector())

    result = list(store.graph.query(f"SELECT ?asset ?event WHERE {{ ?asset <{DEFAULT_NAMESPACE.event}> ?event}}"))

    assert len(result) == 2
    assert result[0][0] == result[1][0]
    assert result[0][1] != result[1][1]
    assert {res[0] for res in result} == {
        DEFAULT_NAMESPACE.Asset_78504378486679,
    }
    assert {res[1] for res in result} == {
        DEFAULT_NAMESPACE.Event_381696371818828,
        DEFAULT_NAMESPACE.Event_381696471818828,
    }


def test_asset_file_connector_transformer_warning():
    store = NeatGraphStore.from_memory_store()

    with pytest.warns(
        UserWarning,
        match="Cannot transform graph store with AssetEventConnector, missing one or more required change",
    ):
        store.transform(transformers.AssetEventConnector())

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml"))

    # Extract time series
    store.write(extractors.EventsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "events.yaml"))

    # Connect assets and time series
    store.transform(transformers.AssetEventConnector())

    with pytest.warns(UserWarning, match="Cannot transform graph store with AssetEventConnector"):
        store.transform(transformers.AssetEventConnector())
