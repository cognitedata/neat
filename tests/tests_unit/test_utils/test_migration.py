from typing import Any

import pytest
from cognite.client.data_classes import Asset
from cognite.client.data_classes.data_modeling import Node

from cognite.neat._utils.migration import as_classic


@pytest.fixture()
def migrated_asset() -> tuple[dict[str, Any], dict[str, Any]]:
    asset = {
        "externalId": "Asset 105876",
        "name": "347",
        "parentId": 1331482884473656,
        "parentExternalId": "Asset 12966",
        "description": "Lube oil system",
        "dataSetId": 1533183997317,
        "metadata": {
            "Class Description": "HIERARCHY",
            "Classification": "HIER",
            "GL Account": "287839.0000.109.??????.???",
            "P&ID": "KL47DSF3001",
            "Primary Craft": "ROTATING",
            "Primary OTSU": "A1-20.01",
            "Priority": "99",
            "PublishEventDate": "2024-12-03T21:13:31.186Z",
            "Site": "KL47",
            "Unit": "DS",
            "lastUpdatedTime": "2024-12-03 21:18:45.869",
            "locationLocationsID": "105876",
            "locationParentID": "12966",
            "location_Location": "DS/NH3/DINGS/628-3-I/728-2-FLOT",
            "site_location": "KL47-DS/NH3/DINGS/628-3-I/728-2-FLOT",
            "site_unit_tag": "KL47-DS-728-2-FLOT",
            "unit_tag": "DS-728-2-FLOT",
        },
        "source": "Source",
        "id": 6883648116577692,
        "createdTime": 1725418203378,
        "lastUpdatedTime": 1739885214893,
        "rootId": 4045609384782306,
    }

    node = {
        "space": "domain_asset",
        "externalId": "Asset 105876",
        "version": 21,
        "lastUpdatedTime": 1740174804685,
        "createdTime": 1740172064293,
        "instanceType": "node",
        "properties": {
            "sp_neat_enterprise": {
                "NeatAsset/v1": {
                    "dataSetId": {"space": "sp_neat_source", "externalId": "DOMAIN_ASSET"},
                    "classicExternalId": "Asset 105876",
                    "path": [
                        {"space": "domain_asset", "externalId": "Asset 12966"},
                        {"space": "domain_asset", "externalId": "Asset 105876"},
                    ],
                    "root": {"space": "domain_asset", "externalId": "Asset 12966"},
                    "parent": {"space": "domain_asset", "externalId": "Asset 12966"},
                    "pathLastUpdatedTime": "2025-02-21T21:53:24.685009+00:00",
                    "name": "347",
                    "description": "Lube oil system",
                    "source": {"space": "sp_neat_source", "externalId": "Source"},
                    "pId": "KL47DSF3001",
                    "Site": "KL47",
                    "Unit": "DS",
                    "Priority": 99,
                    "unit_tag": "DS-728-2-FLOT",
                    "GLAccount": "287839.0000.109.??????.???",
                    "primaryOTSU": "A1-20.01",
                    "primaryCraft": "ROTATING",
                    "site_location": "KL47-DS/NH3/DINGS/628-3-I/728-2-FLOT",
                    "site_unit_tag": "KL47-DS-728-2-FLOT",
                    "Classification": "HIER",
                    "PublishEventDate": "2024-12-03T21:13:31.186+00:00",
                    "classDescription": "HIERARCHY",
                    "locationParentID": 12966,
                    "location_Location": "DS/NH3/DINGS/628-3-I/728-2-FLOT",
                    "mylastUpdatedTime": "2024-12-03T21:18:45.869+00:00",
                    "locationLocationsID": 105876,
                }
            }
        },
        "type": {"space": "sp_neat_enterprise", "externalId": "NeatAsset"},
    }
    return node, asset


class TestAsClassic:
    def test_as_classic_asset(self, migrated_asset: tuple[dict[str, Any], dict[str, Any]]) -> None:
        node_data, asset_data = migrated_asset
        node = Node._load(node_data)
        asset = Asset._load(asset_data)

        assert as_classic(node, asset) == asset
