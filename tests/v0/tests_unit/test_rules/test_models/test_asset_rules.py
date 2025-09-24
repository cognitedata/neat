from datetime import datetime

import pytest

from cognite.neat.v0.core._data_model.models.entities import (
    AssetEntity,
    ConceptEntity,
    RelationshipEntity,
)
from cognite.neat.v0.core._issues.errors import NeatValueError, PropertyDefinitionError


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
            "Concepts": [
                {
                    "Concept": "GeneratingUnit",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#GeneratingUnit",
                    "Match": "exact",
                },
                {
                    "Concept": "ACLineSegment",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#ACLineSegment",
                    "Match": "exact",
                },
            ],
            "Properties": [
                {
                    "Concept": "GeneratingUnit",
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
            "Concepts": [
                {
                    "Concept": "GeneratingUnit",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#GeneratingUnit",
                    "Match": "exact",
                },
                {
                    "Concept": "ACLineSegment",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#ACLineSegment",
                    "Match": "exact",
                },
            ],
            "Properties": [
                {
                    "Concept": "GeneratingUnit",
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
                    "Concept": "ACLineSegment",
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
            "Concepts": [
                {
                    "Concept": "GeneratingUnit",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#GeneratingUnit",
                    "Match": "exact",
                },
                {
                    "Concept": "ACLineSegment",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#ACLineSegment",
                    "Match": "exact",
                },
            ],
            "Properties": [
                {
                    "Concept": "GeneratingUnit",
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
                    "Concept": "ACLineSegment",
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
            ConceptEntity(prefix="power", suffix="ACLineSegment"),
            "class",
            "line",
            "parentExternalId is only allowed to point to a Class not String",
        ),
        id="data_type_for_parent_property",
    )
