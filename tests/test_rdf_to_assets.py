from copy import deepcopy

from cognite.client.data_classes import Asset, AssetList, LabelFilter
from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat.core.extractors.rdf_to_assets import categorize_assets, order_assets


def test_asset_hierarchy_ordering(mock_rdf_assets):
    ordered_assets = [asset.external_id for asset in order_assets(mock_rdf_assets)]
    assert ordered_assets == [
        "RootCIMNode-0",
        "GeographicalRegion-0",
        "SubGeographicalRegion-0",
        "Substation-0",
        "Terminal-0",
        "Terminal-1",
        "orphanage-2626756768281823",
    ]


def test_asset_hierarchy_ordering_orphan(mock_rdf_assets):
    # Make orphan Terminal asset by popping Substation from asset dict
    # This simulates case when new asset is created which already has parent in CDF
    # so we do not need to create parent asset
    mock_rdf_assets.pop("Substation-0")
    ordered_assets = [asset.external_id for asset in order_assets(mock_rdf_assets)]
    assert ordered_assets == [
        "RootCIMNode-0",
        "GeographicalRegion-0",
        "SubGeographicalRegion-0",
        "Terminal-0",
        "Terminal-1",
        "orphanage-2626756768281823",
    ]


def test_asset_diffing(mock_rdf_assets, mock_cdf_assets, transformation_rules):
    rdf_assets = mock_rdf_assets
    cdf_assets = mock_cdf_assets

    # Create non-active asset (aka decommissioned, historic)
    resurrect_id = "GeographicalRegion-0"
    non_active_asset = deepcopy(rdf_assets[resurrect_id])
    non_active_asset["metadata"]["active"] = "false"
    non_active_asset["labels"] = ["GeographicalRegion", "historic"]
    cdf_assets[resurrect_id] = non_active_asset

    # 1 asset to create
    create_id = "Terminal-0"
    cdf_assets.pop(create_id)

    # 1 assets to decommissioned
    decommission_id = "SubGeographicalRegion-0"
    rdf_assets.pop(decommission_id)

    # 1 assets to update
    update_id = "RootCIMNode-0"
    rdf_assets[update_id]["name"] = "Deus Ex Machina"

    with monkeypatch_cognite_client() as client_mock:

        def list_assets(
            data_set_ids: int = 2626756768281823,
            limit: int = -1,
            labels=None,
            **_,
        ):
            labels = labels or LabelFilter(contains_any=["non-historic"])
            if labels == LabelFilter(contains_any=["non-historic"]):
                return AssetList([Asset(**asset) for asset in cdf_assets.values()])
            else:
                return AssetList([Asset(**non_active_asset)])

        client_mock.assets.list = list_assets

    categorized_assets = categorize_assets(client_mock, rdf_assets, transformation_rules.metadata.data_set_id)
    assert len(categorized_assets["create"]) == 1
    assert create_id == categorized_assets["create"][0].external_id

    assert len(categorized_assets["update"]) == 1
    assert update_id == categorized_assets["update"][0].external_id
    assert categorized_assets["update"][0].name == "Deus Ex Machina"

    assert len(categorized_assets["decommission"]) == 1
    assert decommission_id == categorized_assets["decommission"][0].external_id
    assert {label["externalId"] for label in categorized_assets["decommission"][0].labels} == {
        "SubGeographicalRegion",
        "historic",
    }
    assert categorized_assets["decommission"][0].metadata["active"] == "false"

    assert len(categorized_assets["resurrect"]) == 1
    assert resurrect_id == categorized_assets["resurrect"][0].external_id
    assert {label["externalId"] for label in categorized_assets["resurrect"][0].labels} == {
        "GeographicalRegion",
        "non-historic",
    }
    assert categorized_assets["resurrect"][0].metadata["active"] == "true"
