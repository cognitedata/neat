from datetime import datetime
from typing import Any

import pytest

from cognite.neat.rules.models.asset import (
    AssetRules,
)
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import AssetEntity, RelationshipEntity


def case_asset_relationship():
    yield pytest.param(
        {
            "Metadata": {
                "role": "asset architect",
                "schema": "complete",
                "creator": "Jon, Emma, David",
                "namespace": "http://purl.org/cognite/power2consumer",
                "prefix": "power",
                "created": datetime(2024, 2, 9, 0, 0),
                "updated": datetime(2024, 2, 9, 0, 0),
                "version": "0.1.0",
                "title": "Power to Consumer Data Model",
                "license": "CC-BY 4.0",
                "rights": "Free for use",
            },
            "Classes": [
                {
                    "Class": "GeneratingUnit",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#GeneratingUnit",
                    "Match": "exact",
                },
                {
                    "Class": "ACLineSegment",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#ACLineSegment",
                    "Match": "exact",
                },
            ],
            "Properties": [
                {
                    "Class": "GeneratingUnit",
                    "Property": "line",
                    "Description": None,
                    "Value Type": "ACLineSegment",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Transformation": None,
                    "Implementation": "Asset(property=parent_external_id), Relationship(label=cool-label)",
                }
            ],
        },
        [
            AssetEntity.load("Asset(property=parent_external_id)"),
            RelationshipEntity.load("Relationship(label=cool-label)"),
        ],
        id="classic_cdf_mapping",
    )


class TestAssetRules:
    @pytest.mark.parametrize("rules, expected_exception", list(case_asset_relationship()))
    def test_case_insensitivity(self, rules: dict[str, dict[str, Any]], expected_exception: DataType) -> None:
        assert AssetRules.model_validate(rules).properties.data[0].implementation == expected_exception
