from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock

import pytest

from cognite.neat._client.client import NeatClient
from cognite.neat._config import internal_profiles
from cognite.neat._data_model._analysis import CDFSnapshot
from cognite.neat._data_model.importers._table_importer.importer import DMSTableImporter
from cognite.neat._data_model.models.dms._container import ContainerPropertyDefinition, ContainerRequest, ContainerResponse
from cognite.neat._data_model.models.dms._data_model import DataModelRequest
from cognite.neat._data_model.models.dms._data_types import TextProperty
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._references import ContainerReference, DataModelReference, ViewReference
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.models.dms._views import ViewRequest, ViewResponse
from cognite.neat._data_model.validation.dms._ai_readiness import (
    DataModelMissingDescription,
    DataModelMissingName,
    EnumerationMissingDescription,
    EnumerationMissingName,
    ViewMissingDescription,
    ViewMissingName,
    ViewPropertyMissingDescription,
    ViewPropertyMissingName,
)
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._data_model.validation.dms._orchestrator import DmsDataModelValidation

views_as_dicts = [
    dict(
        space="my_space",
        externalId="DomainDescribable",
        version="v1",
        name="My View",
        description="An example view",
        properties={},
        createdTime=0,
        lastUpdatedTime=1,
        writable=True,
        queryable=True,
        usedFor="node",
        isGlobal=False,
        mappedContainers=[{"space": "not_my_space", "externalId": "MyContainer"}],
    ),
    dict(
        space="not_my_space",
        externalId="ExistingEdgeConnection",
        version="v1",
        name="My View",
        description="An example view",
        properties={},
        createdTime=0,
        lastUpdatedTime=1,
        writable=True,
        queryable=True,
        usedFor="node",
        isGlobal=False,
        mappedContainers=[{"space": "not_my_space", "externalId": "MyContainer"}],
    ),
    dict(
        space="my_space",
        externalId="ExistingDirectConnectionRemote",
        version="v1",
        name="My View",
        description="An example view",
        properties={},
        createdTime=0,
        lastUpdatedTime=1,
        writable=True,
        queryable=True,
        usedFor="node",
        isGlobal=False,
        mappedContainers=[{"space": "not_my_space", "externalId": "MyContainer"}],
    ),
    dict(
        space="my_space",
        externalId="SourceForReverseConnectionExistRemote",
        version="v1",
        name="SourceForReverseConnectionExistRemote",
        description="SourceForReverseConnectionExistRemote",
        properties={
            "directPropertyRemote": {
                "container": {"space": "my_space", "externalId": "DirectConnectionRemoteContainer"},
                "containerPropertyIdentifier": "directRemote",
                "type": {
                    "type": "direct",
                    "source": {
                        "space": "my_space",
                        "external_id": "MyDescribable",
                        "version": "v1",
                        "type": "view",
                    },
                },
                "connectionType": "primary_property",
                "constraintState": {"nullability": "current"},
            }
        },
        createdTime=0,
        lastUpdatedTime=1,
        writable=True,
        queryable=True,
        usedFor="node",
        isGlobal=False,
        mappedContainers=[{"space": "not_my_space", "externalId": "MyContainer"}],
    ),
    dict(
        space="prodigy",
        externalId="OutOfSpace",
        version="1992",
        name="Out Of Space",
        description="I'll take your brain to another dimension",
        properties={
            "directPropertyRemote": {
                "container": {"space": "my_space", "externalId": "DirectConnectionRemoteContainer"},
                "containerPropertyIdentifier": "directRemote",
                "type": {
                    "type": "direct",
                    "source": {
                        "space": "my_space",
                        "external_id": "MyDescribable",
                        "version": "v1",
                        "type": "view",
                    },
                },
                "connectionType": "primary_property",
                "constraintState": {"nullability": "current"},
            }
        },
        createdTime=0,
        lastUpdatedTime=1,
        writable=True,
        queryable=True,
        usedFor="node",
        isGlobal=False,
        mappedContainers=[{"space": "not_my_space", "externalId": "MyContainer"}],
    ),
]

containers_as_dicts = [
                dict(
                    space="nospace",
                    externalId="ExistingContainer",
                    name="ExistingContainer",
                    description="ExistingContainer",
                    usedFor="node",
                    properties={
                        "unused": {
                            "type": {"type": "text"},
                            "nullable": False,
                            "immutable": False,
                        }
                    },
                    createdTime=0,
                    lastUpdatedTime=1,
                    isGlobal=False,
                ),
                dict(
                    space="cdf_cdm",
                    externalId="CogniteDescribable",
                    name="ExistingContainer",
                    description="ExistingContainer",
                    usedFor="node",
                    properties={
                        "name": {
                            "type": {"type": "text"},
                            "nullable": False,
                            "immutable": False,
                        }
                    },
                    createdTime=0,
                    lastUpdatedTime=1,
                    isGlobal=False,
                ),
                dict(
                    space="my_space",
                    externalId="DirectConnectionRemoteContainer",
                    name="DirectConnectionRemoteContainer",
                    description="DirectConnectionRemoteContainer",
                    usedFor="node",
                    properties={
                        "directRemote": {
                            "type": {"type": "direct"},
                            "nullable": False,
                            "immutable": False,
                        }
                    },
                    createdTime=0,
                    lastUpdatedTime=1,
                    isGlobal=False,
                ),
            ]




CDF_SNAPSHOT = CDFSnapshot(
    views={ViewReference(**view_dict): ViewResponse(**view_dict).as_request() for view_dict in views_as_dicts},
    containers={ContainerReference(**container_dict): ContainerResponse(**container_dict).as_request() for container_dict in containers_as_dicts},
    # data_models={DataModelReference(space="cdf_cdm", externalId="CogniteCore", version="v1"): DataModelRequest(space="cdf_cdm", externalId="CogniteCore", version="v1", views=[])}
)

CDF_SNAPSHOT.data_models = {DataModelReference(space="cdf_cdm", externalId="CogniteCore", version="v1"): DataModelRequest(space="cdf_cdm", externalId="CogniteCore", version="v1", views=list(CDF_SNAPSHOT.views.keys()))}


@pytest.fixture(scope="session")
def ai_issues() -> tuple[str, dict[type[DataModelValidator], set[str]]]:
    yaml_content = """Metadata:
- Key: space
  Value: cdf_cdm
- Key: externalId
  Value: CogniteCore
- Key: version
  Value: v1
Properties:
- View: CogniteDescribable
  View Property: name
  Value Type: text(maxTextSize=400)
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: CogniteDescribable
  Container Property: name
  Index: btree:name(cursorable=False)
  Constraint: uniqueness:uniqueName(bySpace=True)
  Connection: null

- View: CogniteAsset
  View Property: files
  Connection: reverse(property=assets)
  Value Type: CogniteFile
  Min Count: 0
  Max Count: null

- View: CogniteFile
  View Property: assets
  Connection: direct
  Value Type: CogniteAsset
  Min Count: 0
  Max Count: 1200
  Immutable: false
  Container: CogniteFile
  Container Property: assets

- View: CogniteFile
  View Property: equipments
  Connection: direct
  Value Type: '#N/A'
  Min Count: 0
  Max Count: 1200
  Immutable: false
  Container: CogniteFile
  Container Property: equipments

- View: CogniteFile
  View Property: assetAnnotations
  Connection: edge(edgeSource=FileAnnotation,type=diagramAnnotation)
  Value Type: CogniteAsset
  Min Count: 0
  Max Count: null

- View: CogniteFile
  View Property: category
  Value Type: enum(collection=CogniteFile.category,unknownValue=other)
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: CogniteFile
  Container Property: category
  Container Property Name: category_405
  Connection: null

- View: FileAnnotation
  View Property: confidence
  Value Type: float32
  Min Count: 0
  Max Count: 1
  Immutable: true
  Container: FileAnnotation
  Container Property: confidence
  Connection: null
Views:
- View: CogniteDescribable
- View: CogniteAsset
  Implements: CogniteDescribable
- View: CogniteFile
  Implements: CogniteDescribable
- View: FileAnnotation
  Implements: CogniteDescribable
Containers:
- Container: CogniteDescribable
  Used For: all
- Container: CogniteFile
  Constraint: requires:describablePresent(require=CogniteDescribable)
  Used For: node
- Container: FileAnnotation
  Constraint: requires:describablePresent(require=CogniteDescribable)
  Used For: edge
Enum:
- Collection: CogniteFile.category
  Value: blueprint
- Collection: CogniteFile.category
  Value: document
- Collection: CogniteFile.category
  Value: other
Nodes:
- Node: diagramAnnotation
"""
    expected_problems = {
        DataModelMissingDescription: {"Data model is missing a description."},
        DataModelMissingName: {"Data model is missing a human-readable name."},
        ViewMissingDescription: {"CogniteDescribable", "CogniteAsset", "CogniteFile", "FileAnnotation"},
        ViewMissingName: {"CogniteDescribable", "CogniteAsset", "CogniteFile", "FileAnnotation"},
        ViewPropertyMissingDescription: {
            "name",
            "files",
            "assets",
            "equipments",
            "assetAnnotations",
            "category",
            "confidence",
        },
        ViewPropertyMissingName: {
            "name",
            "files",
            "assets",
            "equipments",
            "assetAnnotations",
            "category",
            "confidence",
        },
        EnumerationMissingName: {
            ("'blueprint' in property category of container cdf_cdm:CogniteFile is missing a human-readable name"),
            ("'document' in property category of container cdf_cdm:CogniteFile is missing a human-readable name"),
            ("'other' in property category of container cdf_cdm:CogniteFile is missing a human-readable name"),
        },
        EnumerationMissingDescription: {
            (
                "'blueprint' in property category of container cdf_cdm:CogniteFile"
                " is missing a human-readable description."
            ),
            (
                "'document' in property category of container cdf_cdm:CogniteFile"
                " is missing a human-readable description."
            ),
            ("'other' in property category of container cdf_cdm:CogniteFile is missing a human-readable description."),
        },
    }

    return yaml_content, expected_problems


@pytest.mark.parametrize("profile", ["deep-additive", "legacy-additive"])
def test_validation_deep(
    profile: Literal["deep-additive", "legacy-additive"],
    ai_issues: tuple[str, dict[type[DataModelValidator], set]],
) -> None:
    yaml_content, expected_problematic_reversals = ai_issues

    read_yaml = MagicMock(spec=Path)
    read_yaml.read_text.return_value = yaml_content
    importer = DMSTableImporter.from_yaml(read_yaml)
    data_model = importer.to_data_model()

    config = internal_profiles()[profile]

    mode = config.modeling.mode
    can_run_validator = config.validation.can_run_validator

    # Run on success validators
    on_success = DmsDataModelValidation(
        cdf_snapshot=CDF_SNAPSHOT, limits = SchemaLimits(), modus_operandi=mode, can_run_validator=can_run_validator
    )
    on_success.run(data_model)
    by_code = on_success.issues.by_code()

    subset_problematic = {
        class_: expected_problematic_reversals[class_]
        for class_ in expected_problematic_reversals.keys()
        if can_run_validator(class_.code, class_.issue_type)
    }
    assert set(class_.code for class_ in subset_problematic.keys()) - set(by_code.keys()) == set()

    # here we check that all expected problematic reversals are found
    found = set()
    actual = set()
    for class_, errors in subset_problematic.items():
        for error in errors:
            actual.add(error)
            for issue in by_code[class_.code]:
                if error in issue.message:
                    found.add(error)
                    break

    assert found == actual
