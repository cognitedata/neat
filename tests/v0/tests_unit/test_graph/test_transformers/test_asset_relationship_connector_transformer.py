from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._instances import extractors, transformers
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._store import NeatInstanceStore
from tests.v0.data import InstanceData


def test_asset_relationship_connector_transformer():
    store = NeatInstanceStore.from_memory_store()
    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml, identifier="externalId"))
    # Extract time series
    store.write(
        extractors.RelationshipsExtractor.from_file(
            InstanceData.AssetCentricCDF.relationships_yaml, identifier="externalId"
        )
    )

    # Connect assets and time series
    store.transform(transformers.AssetRelationshipConnector())

    result = list(
        store.dataset.query(
            f"SELECT ?sourceAsset ?targetAsset WHERE {{ ?sourceAsset <{DEFAULT_NAMESPACE.relationship}> ?targetAsset}}"
        )
    )

    assert len(result) == 3

    assert {res[0] for res in result} == {
        DEFAULT_NAMESPACE["Asset_2dd9048c-bdfb-11e5-94fa-c8f73332c8f4"],
        DEFAULT_NAMESPACE["Asset_f17696ca-9aeb-11e5-91da-b8763fd99c5f"],
        DEFAULT_NAMESPACE["Asset_f17696cf-9aeb-11e5-91da-b8763fd99c5f"],
    }
    assert {res[1] for res in result} == {
        DEFAULT_NAMESPACE["Asset_2dd9048c-bdfb-11e5-94fa-c8f73332c8f4"],
        DEFAULT_NAMESPACE["Asset_f17696cf-9aeb-11e5-91da-b8763fd99c5f"],
        DEFAULT_NAMESPACE["Asset_room-cim-node"],
    }


def test_asset_relationship_connector_transformer_warning():
    store = NeatInstanceStore.from_memory_store()

    issues1 = store.transform(transformers.AssetRelationshipConnector())
    assert len(issues1) == 1
    assert issues1[0] == NeatValueError(
        "Cannot transform graph store with AssetRelationshipConnector, missing one or more required changes "
        "AssetsExtractor and RelationshipsExtractor"
    )

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(InstanceData.AssetCentricCDF.assets_yaml))

    # Extract time series
    store.write(extractors.RelationshipsExtractor.from_file(InstanceData.AssetCentricCDF.relationships_yaml))

    # Connect assets and time series
    store.transform(transformers.AssetRelationshipConnector())

    issues2 = store.transform(transformers.AssetRelationshipConnector())
    assert len(issues2) == 1
    assert issues2[0] == NeatValueError("Cannot transform graph store with AssetRelationshipConnector, already applied")
