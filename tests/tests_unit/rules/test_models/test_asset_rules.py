from datetime import datetime
from typing import Any

import pytest

from cognite.neat.issues import NeatError
from cognite.neat.issues.errors import InvalidPropertyDefinitionError, NeatValueError
from cognite.neat.rules.models import AssetRules, InformationRules
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import AssetEntity, ClassEntity, RelationshipEntity


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
                    "Implementation": "Asset(property=parentExternalId), Relationship(label=cool-label)",
                }
            ],
        },
        [
            AssetEntity.load("Asset(property=parentExternalId)"),
            RelationshipEntity.load("Relationship(label=cool-label)"),
        ],
        id="classic_cdf_mapping",
    )


def case_circular_dependency():
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
                    "Implementation": "Asset(property=parentExternalId)",
                },
                {
                    "Class": "ACLineSegment",
                    "Property": "line",
                    "Description": None,
                    "Value Type": "GeneratingUnit",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Transformation": None,
                    "Implementation": "Asset(property=parentExternalId)",
                },
            ],
        },
        NeatValueError(
            "Invalid Asset Hierarchy, circular dependency detected: [class(prefix=power,"
            "suffix=GeneratingUnit), class(prefix=power,suffix=ACLineSegment), "
            "class(prefix=power,suffix=GeneratingUnit)]"
        ),
        id="circular_dependency",
    )


def parent_property_points_to_data_type():
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
                    "Implementation": "Asset(property=parentExternalId)",
                },
                {
                    "Class": "ACLineSegment",
                    "Property": "line",
                    "Description": None,
                    "Value Type": "string",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Transformation": None,
                    "Implementation": "Asset(property=parentExternalId)",
                },
            ],
        },
        InvalidPropertyDefinitionError(
            ClassEntity(prefix="power", suffix="ACLineSegment"),
            "class",
            "line",
            "parentExternalId is only allowed to point to a Class not String",
        ),
        id="data_type_for_parent_property",
    )


class TestAssetRules:
    @pytest.mark.parametrize("rules, expected_exception", list(case_asset_relationship()))
    def test_case_insensitivity(self, rules: dict[str, dict[str, Any]], expected_exception: DataType) -> None:
        assert AssetRules.model_validate(rules).properties.data[0].implementation == expected_exception

    def test_conversion_between_roles(self, david_rules: InformationRules) -> None:
        asset_rules = david_rules.as_asset_architect_rules()
        information_rules = asset_rules.as_information_rules()

        assert asset_rules.model_dump() == information_rules.as_asset_architect_rules().model_dump()

    @pytest.mark.parametrize("invalid_rules, expected_exception", list(case_circular_dependency()))
    def test_circular_dependency(self, invalid_rules: dict[str, dict[str, Any]], expected_exception: NeatError) -> None:
        with pytest.raises(ValueError) as e:
            AssetRules.model_validate(invalid_rules)
        errors = NeatError.from_pydantic_errors(e.value.errors())
        assert errors[0] == expected_exception

    @pytest.mark.parametrize("invalid_rules, expected_exception", list(parent_property_points_to_data_type()))
    def test_data_type_for_parent_property(
        self, invalid_rules: dict[str, dict[str, Any]], expected_exception: NeatError
    ) -> None:
        with pytest.raises(ValueError) as e:
            AssetRules.model_validate(invalid_rules)
        errors = NeatError.from_pydantic_errors(e.value.errors())
        assert errors[0] == expected_exception
