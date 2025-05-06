from datetime import datetime

import pytest

from cognite.neat.core._issues.errors import NeatValueError, PropertyDefinitionError
from cognite.neat.core._rules.models.entities import (
    AssetEntity,
    ClassEntity,
    RelationshipEntity,
)


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
        PropertyDefinitionError(
            ClassEntity(prefix="power", suffix="ACLineSegment"),
            "class",
            "line",
            "parentExternalId is only allowed to point to a Class not String",
        ),
        id="data_type_for_parent_property",
    )
