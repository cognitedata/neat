from collections.abc import Iterable

import pytest

from cognite.neat._data_model.importers import DMSTableImporter
from cognite.neat._data_model.importers._table_importer.source import TableSource
from cognite.neat._data_model.models.dms import (
    BtreeIndex,
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelRequest,
    DirectNodeRelation,
    EnumProperty,
    EnumValue,
    Float32Property,
    MultiEdgeProperty,
    MultiReverseDirectRelationPropertyRequest,
    NodeReference,
    RequestSchema,
    SpaceRequest,
    TextProperty,
    UniquenessConstraintDefinition,
    ViewCorePropertyRequest,
    ViewDirectReference,
    ViewReference,
    ViewRequest,
)
from cognite.neat._exceptions import ModelImportError
from cognite.neat._utils.useful_types import CellValue

SOURCE = "pytest.xlsx"


def valid_dms_table_formats() -> Iterable[tuple]:
    yield pytest.param(
        {
            "Metadata": [
                {
                    "Name": "space",
                    "Value": "cdf_cdm",
                },
                {
                    "Name": "externalId",
                    "Value": "CogniteCore",
                },
                {
                    "Name": "version",
                    "Value": "v1",
                },
                {
                    "Name": "name",
                    "Value": "Cognite Core Data Model",
                },
                {
                    "Name": "description",
                    "Value": "The Cognite Core Data Model (CDM) is a standardized data model for industrial data.",
                },
            ],
            "Properties": [
                {
                    "View": "CogniteDescribable",
                    "View Property": "name",
                    "Name": None,
                    "Description": None,
                    "Connection": None,
                    "Value Type": "text(maxTextSize=400)",
                    "Min Count": 0,
                    "Max Count": 1,
                    "Immutable": False,
                    "Default": None,
                    "Container": "CogniteDescribable",
                    "Container Property": "name",
                    "Index": "btree:name(cursorable=False)",
                    "Constraint": "uniqueness:uniqueName(bySpace=True)",
                },
                {
                    "View": "CogniteFile",
                    "View Property": "assets",
                    "Name": None,
                    "Description": None,
                    "Connection": "direct",
                    "Value Type": "CogniteAsset",
                    "Min Count": 0,
                    "Max Count": 1200,
                    "Immutable": False,
                    "Default": None,
                    "Container": "CogniteFile",
                    "Container Property": "assets",
                    "Index": None,
                    "Constraint": None,
                },
                {
                    "View": "CogniteFile",
                    "View Property": "assetAnnotations",
                    "Name": None,
                    "Description": None,
                    "Connection": "edge(edgeSource=FileAnnotation,direction=outwards,type=diagramAnnotation)",
                    "Value Type": "CogniteAsset",
                    "Min Count": 0,
                    "Max Count": None,
                    "Immutable": False,
                    "Default": None,
                    "Container": None,
                    "Container Property": None,
                    "Index": None,
                    "Constraint": None,
                },
                {
                    "View": "CogniteFile",
                    "View Property": "category",
                    "Name": None,
                    "Description": None,
                    "Connection": None,
                    "Value Type": "enum(collection=CogniteFile.category,unknownValue=other)",
                    "Min Count": 0,
                    "Max Count": 1,
                    "Immutable": False,
                    "Default": None,
                    "Container": "CogniteFile",
                    "Container Property": "category",
                    "Container Property Name": "category_405",
                    "Index": None,
                    "Constraint": None,
                },
                {
                    "View": "CogniteAsset",
                    "View Property": "files",
                    "Name": None,
                    "Description": None,
                    "Connection": "reverse(property=assets)",
                    "Value Type": "CogniteFile",
                    "Min Count": 0,
                    "Max Count": None,
                    "Immutable": False,
                    "Default": None,
                    "Container": None,
                    "Container Property": None,
                    "Index": None,
                    "Constraint": None,
                },
                {
                    "View": "FileAnnotation",
                    "View Property": "confidence",
                    "Name": None,
                    "Description": None,
                    "Connection": None,
                    "Value Type": "float32",
                    "Min Count": 0,
                    "Max Count": 1,
                    "Immutable": True,
                    "Default": None,
                    "Container": "FileAnnotation",
                    "Container Property": "confidence",
                    "Index": None,
                    "Constraint": None,
                },
            ],
            "Views": [
                {
                    "View": "CogniteDescribable",
                    "Name": "Cognite Describable",
                    "Description": "The describable core concept is used as a standard way of "
                    "holding the bare minimum of information about the instance",
                    "Implements": None,
                    "Filter": None,
                },
                {
                    "View": "CogniteAsset",
                    "Name": "Cognite Asset",
                    "Description": None,
                    "Implements": "CogniteDescribable",
                    "Filter": None,
                },
                {
                    "View": "CogniteFile",
                    "Name": "Cognite File",
                    "Description": None,
                    "Implements": "CogniteDescribable",
                    "Filter": None,
                },
                {
                    "View": "FileAnnotation",
                    "Name": "File Annotation",
                    "Description": None,
                    "Implements": "CogniteDescribable",
                    "Filter": None,
                },
            ],
            "Containers": [
                {
                    "Container": "CogniteDescribable",
                    "Name": None,
                    "Description": None,
                    "Constraint": None,
                    "Used For": "all",
                },
                {
                    "Container": "CogniteFile",
                    "Name": None,
                    "Description": None,
                    "Constraint": "CogniteDescribable",
                    "Used For": "node",
                },
                {
                    "Container": "FileAnnotation",
                    "Name": None,
                    "Description": None,
                    "Constraint": "CogniteDescribable",
                    "Used For": "edge",
                },
            ],
            "Enum": [
                {
                    "Collection": "CogniteFile.category",
                    "Value": "blueprint",
                    "Name": "Blueprint",
                    "Description": "A technical drawing",
                },
                {
                    "Collection": "CogniteFile.category",
                    "Value": "document",
                    "Name": None,
                    "Description": None,
                },
                {
                    "Collection": "CogniteFile.category",
                    "Value": "other",
                    "Name": None,
                    "Description": None,
                },
            ],
            "Nodes": [
                {
                    "Node": "diagramAnnotation",
                }
            ],
        },
        RequestSchema(
            dataModel=DataModelRequest(
                space="cdf_cdm",
                externalId="CogniteCore",
                version="v1",
                name="Cognite Core Data Model",
                description="The Cognite Core Data Model (CDM) is a standardized data model for industrial data.",
                views=[
                    ViewReference(space="cdf_cdm", externalId="CogniteDescribable", version="v1"),
                    ViewReference(space="cdf_cdm", externalId="CogniteAsset", version="v1"),
                    ViewReference(space="cdf_cdm", externalId="CogniteFile", version="v1"),
                    ViewReference(space="cdf_cdm", externalId="FileAnnotation", version="v1"),
                ],
            ),
            spaces=[SpaceRequest(space="cdf_cdm")],
            views=[
                ViewRequest(
                    space="cdf_cdm",
                    externalId="CogniteDescribable",
                    version="v1",
                    name="Cognite Describable",
                    description="The describable core concept is used as a standard way of holding the bare minimum "
                    "of information about the instance",
                    implements=None,
                    properties={
                        "name": ViewCorePropertyRequest(
                            name=None,
                            description=None,
                            container=ContainerReference(space="cdf_cdm", externalId="CogniteDescribable"),
                            containerPropertyIdentifier="name",
                        ),
                    },
                ),
                ViewRequest(
                    space="cdf_cdm",
                    externalId="CogniteAsset",
                    version="v1",
                    name="Cognite Asset",
                    description=None,
                    implements=[ViewReference(space="cdf_cdm", externalId="CogniteDescribable", version="v1")],
                    properties={
                        "files": MultiReverseDirectRelationPropertyRequest(
                            name=None,
                            description=None,
                            source=ViewReference(space="cdf_cdm", externalId="CogniteFile", version="v1"),
                            through=ViewDirectReference(
                                source=ViewReference(space="cdf_cdm", externalId="CogniteFile", version="v1"),
                                identifier="assets",
                            ),
                        ),
                    },
                ),
                ViewRequest(
                    space="cdf_cdm",
                    externalId="CogniteFile",
                    version="v1",
                    name="Cognite File",
                    description=None,
                    implements=[ViewReference(space="cdf_cdm", externalId="CogniteDescribable", version="v1")],
                    properties={
                        "assets": ViewCorePropertyRequest(
                            name=None,
                            description=None,
                            container=ContainerReference(space="cdf_cdm", externalId="CogniteFile"),
                            containerPropertyIdentifier="assets",
                            source=ViewReference(space="cdf_cdm", externalId="CogniteAsset", version="v1"),
                        ),
                        "assetAnnotations": MultiEdgeProperty(
                            name=None,
                            description=None,
                            source=ViewReference(space="cdf_cdm", externalId="CogniteAsset", version="v1"),
                            edgeSource=ViewReference(space="cdf_cdm", externalId="FileAnnotation", version="v1"),
                            direction="outwards",
                            type=NodeReference(space="cdf_cdm", externalId="diagramAnnotation"),
                        ),
                        "category": ViewCorePropertyRequest(
                            name=None,
                            description=None,
                            container=ContainerReference(space="cdf_cdm", externalId="CogniteFile"),
                            containerPropertyIdentifier="category",
                        ),
                    },
                ),
                ViewRequest(
                    space="cdf_cdm",
                    externalId="FileAnnotation",
                    version="v1",
                    name="File Annotation",
                    description=None,
                    implements=[ViewReference(space="cdf_cdm", externalId="CogniteDescribable", version="v1")],
                    properties={
                        "confidence": ViewCorePropertyRequest(
                            name=None,
                            description=None,
                            container=ContainerReference(space="cdf_cdm", externalId="FileAnnotation"),
                            containerPropertyIdentifier="confidence",
                        ),
                    },
                ),
            ],
            containers=[
                ContainerRequest(
                    space="cdf_cdm",
                    externalId="CogniteDescribable",
                    usedFor="all",
                    properties={
                        "name": ContainerPropertyDefinition(
                            immutable=False,
                            nullable=True,
                            autoIncrement=None,
                            defaultValue=None,
                            description=None,
                            name=None,
                            type=TextProperty(list=False, maxTextSize=400),
                        )
                    },
                    indexes={
                        "name": BtreeIndex(properties=["name"], cursorable=False),
                    },
                    constraints={
                        "uniqueName": UniquenessConstraintDefinition(
                            constraint_type="uniqueness",
                            properties=["name"],
                            bySpace=True,
                        )
                    },
                ),
                ContainerRequest(
                    space="cdf_cdm",
                    externalId="CogniteFile",
                    usedFor="node",
                    properties={
                        "assets": ContainerPropertyDefinition(
                            immutable=False,
                            nullable=True,
                            autoIncrement=None,
                            defaultValue=None,
                            description=None,
                            name=None,
                            type=DirectNodeRelation(maxListSize=1200, list=True),
                        ),
                        "category": ContainerPropertyDefinition(
                            immutable=False,
                            nullable=True,
                            autoIncrement=None,
                            defaultValue=None,
                            description=None,
                            name="category_405",
                            type=EnumProperty(
                                unknownValue="other",
                                values={
                                    "blueprint": EnumValue(name="Blueprint", description="A technical drawing"),
                                    "document": EnumValue(),
                                    "other": EnumValue(),
                                },
                            ),
                        ),
                    },
                ),
                ContainerRequest(
                    space="cdf_cdm",
                    externalId="FileAnnotation",
                    usedFor="edge",
                    properties={
                        "confidence": ContainerPropertyDefinition(
                            immutable=True,
                            nullable=True,
                            autoIncrement=None,
                            defaultValue=None,
                            description=None,
                            name=None,
                            type=Float32Property(list=False),
                        )
                    },
                ),
            ],
            nodeTypes=[NodeReference(space="cdf_cdm", externalId="diagramAnnotation")],
        ),
        id="Full example",
    )


def invalid_tmd_table_formats() -> Iterable[tuple]:
    yield pytest.param(
        {
            "Metadata": [
                {
                    "Name": "space",
                    "Value": "cdf_cdm",
                },
                {
                    "Name": "version",
                    "Value": "v1",
                },
            ],
            "Properties": [
                {
                    "View": "CogniteDescribable",
                    "View Property": "name",
                    "Name": None,
                    "Description": None,
                    "Connection": None,
                    "Value Type": "text",
                    "Min Count": 0,
                    "Max Count": 1,
                    "Immutable": False,
                    "Default": None,
                    "Container": "CogniteDescribable",
                    "Container Property": "name",
                    "Index": "btree:name(cursorable=invalid)",
                    "Constraint": None,
                }
            ],
            "Views": [
                {
                    "View": None,
                    "Name": "Cognite Describable",
                    "Description": "The describable core concept is used as a standard way of "
                    "holding the bare minimum of information about the instance",
                    "Implements": None,
                    "Filter": None,
                }
            ],
            "Containers": [
                {
                    "Container": "CogniteDescribable",
                    "Name": None,
                    "Description": None,
                    "Constraint": None,
                    "Used For": "Instances",
                }
            ],
        },
        {
            "In table 'Metadata' missing required value: 'externalId'",
            "In table 'Properties' row 1 column 'Index' -> btree.cursorable input should be "
            "a valid boolean. Got 'invalid' of type str.",
            "In table 'Views' row 1 the column 'View' cannot be empty.",
            "In table 'Containers' row 1 column 'Used For' input should be 'node', 'edge' or 'all'. Got 'Instances'.",
        },
        id="Missing required metadata fields",
    )


class TestDMSTableImporter:
    @pytest.mark.parametrize("data,expected", list(valid_dms_table_formats()))
    def test_import(self, data: dict[str, list[dict[str, CellValue]]], expected: RequestSchema) -> None:
        importer = DMSTableImporter(data)
        result = importer.to_data_model()
        assert result.model_dump() == expected.model_dump()

    @pytest.mark.parametrize("data,expected_errors", list(invalid_tmd_table_formats()))
    def test_import_errors(self, data: dict[str, list[dict[str, CellValue]]], expected_errors: set[str]) -> None:
        importer = DMSTableImporter(data, source=TableSource(source=SOURCE, table_read={}))
        with pytest.raises(ModelImportError) as e:
            _ = importer.to_data_model()

        result_errors = {err.message for err in e.value.errors}

        assert result_errors == expected_errors
