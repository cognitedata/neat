from datetime import datetime
from typing import Any

import pandas as pd
import pytest
from cognite.client import data_modeling as dm

from cognite.neat.rules.models import DMSRules, SheetList
from cognite.neat.rules.models.asset import (
    AssetClass,
    AssetRules,
)
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import AssetEntity, RelationshipEntity
from cognite.neat.utils.spreadsheet import read_individual_sheet
from tests.config import DOC_RULES


@pytest.fixture(scope="session")
def david_spreadsheet() -> dict[str, dict[str, Any]]:
    filepath = DOC_RULES / "information-architect-david.xlsx"
    excel_file = pd.ExcelFile(filepath)
    return {
        "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
        "Properties": read_individual_sheet(excel_file, "Properties", expected_headers=["Property"]),
        "Classes": read_individual_sheet(excel_file, "Classes", expected_headers=["Class"]),
    }


def case_asset_relationship():
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
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


def invalid_domain_rules_cases():
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
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
                }
            ],
            "Properties": [
                {
                    "Class": "GeneratingUnit",
                    "Property": "name",
                    "Description": None,
                    "Value Type": "string",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Transformation": ":GeneratingUnit(cim:name)",
                }
            ],
        },
        (
            ":GeneratingUnit(cim:name) is not a valid rdfpath!"
            "\nFor more information visit: "
            "https://cognite-neat.readthedocs-hosted.com/en/latest/api/exceptions.html#cognite.neat.rules.exceptions.NotValidRDFPath"
        ),
        id="missing_rule",
    )


def incomplete_rules_case():
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
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
                }
            ],
            "Properties": [
                {
                    "Class": "GeneratingUnit2",
                    "Property": "name",
                    "Description": None,
                    "Value Type": "string",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Rule Type": "rdfpath",
                    "Rule": "cim:GeneratingUnit",
                }
            ],
        },
        ("Value error, [PropertiesDefinedForUndefinedClassesError(classes=['power:GeneratingUnit2'])]"),
        id="missing_rule",
    )


class TestAssetRules:
    def test_load_valid_jon_rules(self, david_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = AssetRules.model_validate(david_spreadsheet)

        assert isinstance(valid_rules, AssetRules)

        sample_expected_properties = {
            "power:WindTurbine.manufacturer",
            "power:Substation.secondaryPowerLine",
            "power:WindFarm.exportCable",
        }
        missing = sample_expected_properties - {f"{prop.class_}.{prop.property_}" for prop in valid_rules.properties}
        assert not missing, f"Missing properties: {missing}"

    @pytest.mark.parametrize("invalid_rules, expected_exception", list(invalid_domain_rules_cases()))
    def test_invalid_rules(self, invalid_rules: dict[str, dict[str, Any]], expected_exception: str) -> None:
        with pytest.raises(ValueError) as e:
            AssetRules.model_validate(invalid_rules)
        errors = e.value.errors()
        assert errors[0]["msg"] == expected_exception

    @pytest.mark.parametrize("incomplete_rules, expected_exception", list(incomplete_rules_case()))
    def test_incomplete_rules(self, incomplete_rules: dict[str, dict[str, Any]], expected_exception: str) -> None:
        with pytest.raises(ValueError) as e:
            AssetRules.model_validate(incomplete_rules)
        errors = e.value.errors()
        assert errors[0]["msg"] == expected_exception

    @pytest.mark.parametrize("rules, expected_exception", list(case_asset_relationship()))
    def test_case_insensitivity(self, rules: dict[str, dict[str, Any]], expected_exception: DataType) -> None:
        assert AssetRules.model_validate(rules).properties.data[0].implementation == expected_exception

    def test_david_as_dms(self, david_spreadsheet: dict[str, dict[str, Any]]) -> None:
        david_rules = AssetRules.model_validate(david_spreadsheet)
        dms_rules = david_rules.as_dms_architect_rules()

        assert isinstance(dms_rules, DMSRules)

    def test_olav_as_dms(self, olav_rules: AssetRules) -> None:
        olav_rules_copy = olav_rules.model_copy(deep=True)
        # Todo: Remove this line when Olav's Information .xlsx file is available
        new_classes = SheetList[AssetClass](data=[])
        for cls_ in olav_rules_copy.classes:
            if cls_.class_.versioned_id == "power_analytics:GeoLocation":
                continue
            elif cls_.class_.versioned_id in ("power_analytics:Point", "power_analytics:Polygon"):
                cls_.parent = None
            new_classes.append(cls_)
        olav_rules_copy.classes = new_classes
        ## End of temporary code

        dms_rules = olav_rules_copy.as_dms_architect_rules()

        assert isinstance(dms_rules, DMSRules)
        schema = dms_rules.as_schema()

        wind_turbine = next((view for view in schema.views.values() if view.external_id == "WindTurbine"), None)
        assert wind_turbine is not None
        expected_containers = {
            dm.ContainerId("power", "GeneratingUnit"),
            dm.ContainerId("power", "WindTurbine"),
            dm.ContainerId("power_analytics", "WindTurbine"),
        }
        missing = expected_containers - wind_turbine.referenced_containers()
        assert not missing, f"Missing containers: {missing}"
        extra = wind_turbine.referenced_containers() - expected_containers
        assert not extra, f"Extra containers: {extra}"

        wind_farm = next((view for view in schema.views.values() if view.external_id == "WindFarm"), None)
        assert wind_farm is not None
        expected_containers = {dm.ContainerId("power", "EnergyArea"), dm.ContainerId("power_analytics", "WindFarm")}
        missing = expected_containers - wind_farm.referenced_containers()
        assert not missing, f"Missing containers: {missing}"
        extra = wind_farm.referenced_containers() - expected_containers
        assert not extra, f"Extra containers: {extra}"

        point = next((view for view in schema.views.values() if view.external_id == "Point"), None)
        assert point is not None
        assert point.implements == [dm.ViewId("power", "Point", "0.1.0")]

        polygon = next((view for view in schema.views.values() if view.external_id == "Polygon"), None)
        assert polygon is not None
        assert polygon.implements == [dm.ViewId("power", "Polygon", "0.1.0")]
