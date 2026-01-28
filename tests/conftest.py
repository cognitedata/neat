import pytest


@pytest.fixture
def example_space_statistics_response() -> dict:
    """Example DMS space statistics API response with diverse scenarios."""
    return {
        "items": [
            {
                "space": "production_space",
                "containers": 25,
                "views": 40,
                "dataModels": 5,
                "edges": 15000,
                "softDeletedEdges": 150,
                "nodes": 8000,
                "softDeletedNodes": 80,
            },
            {
                "space": "staging_space",
                "containers": 10,
                "views": 15,
                "dataModels": 2,
                "edges": 1000,
                "softDeletedEdges": 10,
                "nodes": 500,
                "softDeletedNodes": 5,
            },
            {
                "space": "empty_space",
                "containers": 0,
                "views": 0,
                "dataModels": 0,
                "edges": 0,
                "softDeletedEdges": 0,
                "nodes": 0,
                "softDeletedNodes": 0,
            },
            {
                "space": "deleted_only_space",
                "containers": 0,
                "views": 0,
                "dataModels": 0,
                "edges": 0,
                "softDeletedEdges": 50,
                "nodes": 0,
                "softDeletedNodes": 25,
            },
            {
                "space": "dev_space",
                "containers": 3,
                "views": 5,
                "dataModels": 1,
                "edges": 100,
                "softDeletedEdges": 2,
                "nodes": 50,
                "softDeletedNodes": 1,
            },
            {
                "space": "cdf_cdm_units",
                "containers": 0,
                "views": 0,
                "dataModels": 0,
                "edges": 0,
                "softDeletedEdges": 50,
                "nodes": 0,
                "softDeletedNodes": 25,
            },
            {
                "space": "scene",
                "containers": 0,
                "views": 0,
                "dataModels": 0,
                "edges": 0,
                "softDeletedEdges": 50,
                "nodes": 0,
                "softDeletedNodes": 25,
            },
        ]
    }


@pytest.fixture
def example_statistics_response() -> dict:
    """Example DMS statistics API response."""
    return {
        "spaces": {"count": 5, "limit": 100},
        "containers": {"count": 42, "limit": 1000},
        "views": {"count": 123, "limit": 2000},
        "dataModels": {"count": 8, "limit": 500},
        "containerProperties": {"count": 1234, "limit": 100},
        "instances": {
            "edges": 5000,
            "softDeletedEdges": 100,
            "nodes": 10000,
            "softDeletedNodes": 200,
            "instances": 15000,
            "instancesLimit": 5000000,
            "softDeletedInstances": 300,
            "softDeletedInstancesLimit": 10000000,
        },
        "concurrentReadLimit": 10,
        "concurrentWriteLimit": 5,
        "concurrentDeleteLimit": 3,
    }


@pytest.fixture(scope="session")
def valid_dms_toolkit_yaml_format() -> str:
    return """
dataModel:
  space: sp_command_centre_v1
  externalId: CommandCentreModel
  name: Command Centre Prototype V1
  version: v1
  description: >
    The comprehensive Data Model for the Command Centre. It unifies OT, IT,
    Logistics, and Financial data to enable 'Atlas AI' agents to detect
    supply chain risks and simulate mitigation scenarios.
  views:
    - space: sp_command_centre_v1
      externalId: Organization
      version: v1
    - space: cdf_cdm
      externalId: CogniteAsset
      version: v1

views:
- space: sp_command_centre_v1
  externalId: Organization
  name: Organization
  version: v1
  description: The top-level node representing the corporate entity.
  properties:
    name:
      name: Name
      description: The name of the organization.
      container:
        type: container
        space: cdf_cdm
        externalId: CogniteDescribable
      containerPropertyIdentifier: name
    totalRevenueRisk:
      name: Total Revenue Risk
      description: Aggregated financial risk ($) across all regions.
      container:
        type: container
        space: sp_command_centre_v1
        externalId: cont_enterprise_hierarchy
      containerPropertyIdentifier: totalRevenueRisk

containers:
- space: sp_command_centre_v1
  externalId: cont_enterprise_hierarchy
  name: Enterprise Hierarchy Container
  usedFor: node
  properties:
    totalRevenueRisk:
      immutable: false
      nullable: true
      autoIncrement: false
      defaultValue: null
      description: null
      name: null
      type:
        type: float64
        list: false
        maxListSize: null
    globalStockValue:
      immutable: false
      nullable: true
      autoIncrement: false
      defaultValue: null
      description: null
      name: null
      type:
        type: float64
        list: false
        maxListSize: null

spaces:
- space: sp_command_centre_v1
  name: Command Centre Prototype V1
  description: >
    A dedicated space for the Manufacturing Command Centre Knowledge Graph.
    It hosts specific extensions for Supply Chain risk, Financial impact, and
    multi-site Inventory visibility, supporting the 'Derisking Manufacturing Supply Chain' prototype."""


@pytest.fixture(scope="session")
def valid_dms_yaml_format() -> str:
    return """Metadata:
- Key: space
  Value: cdf_cdm
- Key: externalId
  Value: CogniteDataModel
- Key: version
  Value: v1
- Key: description
  Value: Sample Cognite Data Model
- Key: name
  Value: Cognite Data Model
Properties:
- View: CogniteDescribable
  View Property: name
  Name: Name Property
  Description: The name of the describable entity
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: CogniteDescribable
  Container Property: name
  Index: btree:name(cursorable=True)
  Connection: null
Views:
- View: CogniteDescribable
  Name: Describable View
  Description: View for describable entities
Containers:
- Container: CogniteDescribable
  Used For: node
"""


@pytest.fixture(scope="session")
def valid_dms_tabular_yaml_partial() -> str:
    return """Metadata:
- Key: space
  Value: cdf_cdm
- Key: externalId
  Value: CogniteDataModel
- Key: version
  Value: v1
- Key: description
  Value: Sample Cognite Data Model
- Key: name
  Value: Cognite Data Model
Properties:
- View: CogniteDescribable
  View Property: name
  Name: Name Property
  Description: The name of the describable entity
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: CogniteDescribable
  Container Property: name
  Index: btree:name(cursorable=True)
  Connection: null
Views:
- View: CogniteDescribable
  Name: Describable View
  Description: View for describable entities
"""


@pytest.fixture(scope="session")
def model_syntax_error_dms_yaml_format() -> str:
    return """Metadata:
- Key: space
  Value: cdf_cdm
- Key: externalId
  Value: CogniteDataModel
- Key: version
  Value: v1
Properties:
- View: CogniteDescribable
  View Property: name
  Name: Name Property
  Description: The name of the describable entity
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: CogniteDescribable
  Container Property: name
  Index: notValidIndex:name(cursorable=True)
  Connection: null
Views:
- View: CogniteDescribable
Containers:
- Container: CogniteDescribable
  Used For: node
"""


@pytest.fixture(scope="session")
def consistency_error_dms_yaml_format() -> str:
    return """Metadata:
- Key: space
  Value: cdf_cdm
- Key: externalId
  Value: CogniteDataModel
- Key: version
  Value: v1
Properties:
- View: CogniteSourceable
  View Property: name
  Name: Name Property
  Description: The name of the sourceable entity
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: MyNonExistingContainer
  Container Property: sourceSystem
  Index: null
  Connection: null
Views:
- View: CogniteSourceable
"""
