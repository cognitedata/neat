from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._instances import extractors, transformers
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._store import NeatInstanceStore
from tests.v0.data import InstanceData


def test_asset_event_connector_transformer():
    store = NeatInstanceStore.from_memory_store()

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml))

    # Extract time series
    store.write(extractors.EventsExtractor.from_file(InstanceData.AssetCentricCDF.events_yaml))

    # Connect assets and time series
    store.transform(transformers.AssetEventConnector())

    result = list(store.dataset.query(f"SELECT ?asset ?event WHERE {{ ?asset <{DEFAULT_NAMESPACE.event}> ?event}}"))

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
    store = NeatInstanceStore.from_memory_store()

    issues1 = store.transform(transformers.AssetEventConnector())
    assert len(issues1) == 1
    assert issues1[0] == NeatValueError(
        "Cannot transform graph store with AssetEventConnector, missing one or more required changes "
        "AssetsExtractor and EventsExtractor"
    )

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml))

    # Extract time series
    store.write(extractors.EventsExtractor.from_file(InstanceData.AssetCentricCDF.events_yaml))

    # Connect assets and time series
    store.transform(transformers.AssetEventConnector())

    issues2 = store.transform(transformers.AssetEventConnector())

    assert len(issues2) == 1
    assert issues2[0] == NeatValueError("Cannot transform graph store with AssetEventConnector, already applied")
