from copy import deepcopy

import pandas as pd
import pytest
from cognite.client.data_classes import Asset, AssetList, Label, LabelDefinition, LabelDefinitionList, LabelFilter
from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat.legacy.graph.loaders.core.rdf_to_assets import (
    AssetLike,
    NeatMetadataKeys,
    _assets_to_update,
    categorize_assets,
    order_assets,
    remove_non_existing_labels,
)
from cognite.neat.legacy.rules.exporters._core.rules2labels import get_labels


def test_asset_hierarchy_ordering(mock_rdf_assets):
    ordered_assets = [asset.external_id for asset in order_assets(mock_rdf_assets)]
    assert ordered_assets == [
        "RootCIMNode-0",
        "GeographicalRegion-0",
        "SubGeographicalRegion-0",
        "Substation-0",
        "Terminal-0",
        "Terminal-1",
        "orphanage-123456",
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
        "orphanage-123456",
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

        def list_assets(data_set_ids: int = 123456, limit: int = -1, labels=None, **_):
            labels = labels or LabelFilter(contains_any=["non-historic"])
            if labels == LabelFilter(contains_any=["non-historic"]):
                return AssetList([Asset(**asset) for asset in cdf_assets.values()])
            else:
                return AssetList([Asset(**non_active_asset)])

        def list_labels(**_):
            label_names = [*list(get_labels(transformation_rules)), "non-historic", "historic"]
            return [Label(external_id=label_name, name=label_names) for label_name in label_names]

        client_mock.assets.list = list_assets
        client_mock.labels.list = list_labels

    categorized_assets, report = categorize_assets(client_mock, rdf_assets, data_set_id=123456, return_report=True)
    assert len(categorized_assets["create"]) == 1
    assert len(report["create"]) == 1
    assert create_id == categorized_assets["create"][0].external_id
    assert create_id in report["create"]

    assert len(categorized_assets["update"]) == 1
    assert len(report["update"]) == 1
    assert update_id == categorized_assets["update"][0].external_id
    assert update_id in report["update"]
    assert categorized_assets["update"][0].name == "Deus Ex Machina"
    assert report["update"][update_id] == {
        "values_changed": {"root['name']": {"new_value": "Deus Ex Machina", "old_value": "RootCIMNode 0"}}
    }

    assert len(categorized_assets["decommission"]) == 1
    assert len(report["decommission"]) == 1
    assert decommission_id == categorized_assets["decommission"][0].external_id
    assert decommission_id in report["decommission"]
    assert {label.external_id for label in categorized_assets["decommission"][0].labels} == {
        "SubGeographicalRegion",
        "historic",
    }
    assert categorized_assets["decommission"][0].metadata["active"] == "false"

    assert len(categorized_assets["resurrect"]) == 1
    assert len(report["resurrect"]) == 1
    assert resurrect_id == categorized_assets["resurrect"][0].external_id
    assert resurrect_id in report["resurrect"]
    assert {label.external_id for label in categorized_assets["resurrect"][0].labels} == {
        "GeographicalRegion",
        "non-historic",
    }
    assert categorized_assets["resurrect"][0].metadata["active"] == "true"


def generate_remove_non_existing_labels_test_data():
    labels = LabelDefinitionList([LabelDefinition(external_id="historic", name="historic")])
    assets = Asset(external_id="office1", name="Office 1")
    yield pytest.param(labels, [assets], [assets], id="Asset without label")


@pytest.mark.parametrize("cdf_labels, assets, expected_assets", list(generate_remove_non_existing_labels_test_data()))
def test_remove_non_existing_labels(cdf_labels: LabelDefinitionList, assets: AssetLike, expected_assets: AssetLike):
    # Arrange
    with monkeypatch_cognite_client() as client:
        client.labels.list.return_value = cdf_labels

        # Act
        actual_assets = remove_non_existing_labels(client, assets)

    # Assert
    assert actual_assets == expected_assets


def test_neat_metadata_keys_load():
    # Arrange
    input_data = {"start_time": "beginning_time", "invalid_keys": "not valid"}
    expected = NeatMetadataKeys(start_time="beginning_time")

    # Act
    actual = NeatMetadataKeys.load(input_data)

    # Arrange
    assert actual == expected


def test_neat_metadata_keys_alias():
    # Arrange
    keys = NeatMetadataKeys(type="category")
    expected = dict(
        start_time="start_time",
        end_time="end_time",
        update_time="update_time",
        resurrection_time="resurrection_time",
        identifier="identifier",
        active="active",
        type="category",
    )
    # Act
    aliases = keys.as_aliases()

    # Assert
    assert aliases == expected


def test_assets_to_update(mock_rdf_assets, mock_cdf_assets):
    rdf_assets = mock_rdf_assets
    rdf_asset_ids = set(rdf_assets.keys())
    cdf_assets = mock_cdf_assets

    rdf_assets["Terminal-0"]["parent_external_id"] = "Substation-0"
    cdf_assets["Terminal-0"]["parent_external_id"] = "Substation-1"
    cdf_assets_df = pd.DataFrame.from_records([asset for asset in cdf_assets.values()])

    assets, report = _assets_to_update(
        rdf_assets=rdf_assets, cdf_assets=cdf_assets_df, asset_ids=rdf_asset_ids, meta_keys=NeatMetadataKeys()
    )

    expected_report = {
        "Terminal-0": {
            "values_changed": {"root['parent_external_id']": {"new_value": "Substation-0", "old_value": "Substation-1"}}
        }
    }

    assert report == expected_report
    assert len(assets) == 1
