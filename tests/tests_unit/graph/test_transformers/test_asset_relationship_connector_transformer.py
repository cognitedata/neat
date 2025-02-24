import pytest

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._graph import extractors, transformers
from cognite.neat._store import NeatGraphStore
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_asset_relationship_connector_transformer():
    store = NeatGraphStore.from_memory_store()
    # Extract assets
    store.write(
        extractors.AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml", identifier="externalId")
    )
    # Extract time series
    store.write(
        extractors.RelationshipsExtractor.from_file(
            CLASSIC_CDF_EXTRACTOR_DATA / "relationships.yaml", identifier="externalId"
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
    store = NeatGraphStore.from_memory_store()

    with pytest.warns(
        UserWarning,
        match="Cannot transform graph store with AssetRelationshipConnector, missing one or more required change",
    ):
        store.transform(transformers.AssetRelationshipConnector())

    # Extract assets
    store.write(extractors.AssetsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "assets.yaml"))

    # Extract time series
    store.write(extractors.RelationshipsExtractor.from_file(CLASSIC_CDF_EXTRACTOR_DATA / "relationships.yaml"))

    # Connect assets and time series
    store.transform(transformers.AssetRelationshipConnector())

    with pytest.warns(UserWarning, match="Cannot transform graph store with AssetRelationshipConnector"):
        store.transform(transformers.AssetRelationshipConnector())
