from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph import extractors, transformers
from cognite.neat.graph.stores import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_asset_ts_connector_transformer():
    store = NeatGraphStore.from_memory_store()

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml"))

    # Extract time series
    store.write(extractors.TimeSeriesExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "timeseries.yaml"))

    # Connect assets and time series
    store.transform(transformers.AssetTimeSeriesConnector())

    result = list(store.graph.query(f"SELECT ?asset ?ts WHERE {{ ?asset <{DEFAULT_NAMESPACE.timeSeries}> ?ts}}"))

    assert len(result) == 2
    assert result[0][0] == result[1][0]
    assert result[0][0] == DEFAULT_NAMESPACE.Asset_78504378486679
    assert result[0][1] != result[1][1]
    assert {res[1] for res in result} == {
        DEFAULT_NAMESPACE.TimeSeries_7075848883606566,
        DEFAULT_NAMESPACE.TimeSeries_7015848883606566,
    }
