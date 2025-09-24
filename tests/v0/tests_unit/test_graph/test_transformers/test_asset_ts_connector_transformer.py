from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._instances import extractors, transformers
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._store import NeatInstanceStore
from tests.v0.data import InstanceData


def test_asset_ts_connector_transformer():
    store = NeatInstanceStore.from_memory_store()

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml))

    # Extract time series
    store.write(extractors.TimeSeriesExtractor.from_file(InstanceData.AssetCentricCDF.timeseries_yaml))

    # Connect assets and time series
    store.transform(transformers.AssetTimeSeriesConnector())

    result = list(store.dataset.query(f"SELECT ?asset ?ts WHERE {{ ?asset <{DEFAULT_NAMESPACE.timeSeries}> ?ts}}"))

    assert len(result) == 2
    assert result[0][0] == result[1][0]
    assert result[0][0] == DEFAULT_NAMESPACE.Asset_78504378486679
    assert result[0][1] != result[1][1]
    assert {res[1] for res in result} == {
        DEFAULT_NAMESPACE.TimeSeries_7075848883606566,
        DEFAULT_NAMESPACE.TimeSeries_7015848883606566,
    }


def test_asset_ts_connector_transformer_warning():
    store = NeatInstanceStore.from_memory_store()

    issues1 = store.transform(transformers.AssetTimeSeriesConnector())
    assert len(issues1) == 1
    assert issues1[0] == NeatValueError(
        "Cannot transform graph store with AssetTimeSeriesConnector, missing one or more required "
        "changes AssetsExtractor and TimeSeriesExtractor"
    )

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml))

    # Extract time series
    store.write(extractors.TimeSeriesExtractor.from_file(InstanceData.AssetCentricCDF.timeseries_yaml))

    # Connect assets and time series
    store.transform(transformers.AssetTimeSeriesConnector())

    issues2 = store.transform(transformers.AssetTimeSeriesConnector())
    assert len(issues2) == 1
    assert issues2[0] == NeatValueError("Cannot transform graph store with AssetTimeSeriesConnector, already applied")
