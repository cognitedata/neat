from typing import Any

import pytest
import respx
from cognite.client import ClientConfig
from cognite.client.credentials import Token

from cognite.neat._client import NeatClient, NeatClientConfig
from cognite.neat._data_model.models.dms import (
    ContainerResponse,
    DataModelResponse,
    SpaceResponse,
    ViewResponse,
)

BASE_URL = "http://neat.cognitedata.com"


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
def neat_config() -> NeatClientConfig:
    return NeatClientConfig(
        ClientConfig(
            client_name="test-client",
            project="test-project",
            base_url=BASE_URL,
            max_workers=1,
            timeout=10,
            credentials=Token("abc"),
        )
    )


@pytest.fixture(scope="session")
def neat_client(neat_config: NeatClientConfig) -> NeatClient:
    return NeatClient(neat_config)


@pytest.fixture
def validation_test_cdf_client(
    neat_client: NeatClient, example_statistics_response: dict, respx_mock: respx.MockRouter
) -> NeatClient:
    client = neat_client
    config = client.config
    respx_mock.post(
        config.create_api_url("/models/datamodels/byids"),
    ).respond(
        status_code=200,
        json={
            "items": [],
            "nextCursor": None,
        },
    )
    respx_mock.post(
        config.create_api_url("/models/views/byids?includeInheritedProperties=true"),
    ).respond(
        status_code=200,
        json={
            "items": [
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
            ],
            "nextCursor": None,
        },
    )
    respx_mock.post(
        config.create_api_url("/models/containers/byids"),
    ).respond(
        status_code=200,
        json={
            "items": [
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
            ],
            "nextCursor": None,
        },
    )
    respx_mock.get(
        config.create_api_url("/models/statistics"),
    ).respond(
        status_code=200,
        json=example_statistics_response,
    )

    return client


@pytest.fixture
def example_dms_data_model_response() -> dict[str, Any]:
    return dict(
        space="my_space",
        externalId="my_data_model",
        version="v1",
        name="My Data Model",
        description="An example data model",
        views=[
            dict(
                space="my_space",
                externalId="MyView",
                version="v1",
            )
        ],
        createdTime=0,
        lastUpdatedTime=1,
        isGlobal=False,
    )


@pytest.fixture
def example_dms_view_response() -> dict[str, Any]:
    return dict(
        space="my_space",
        externalId="MyView",
        version="v1",
        name="My View",
        description="An example view",
        properties={
            "name": {
                "container": {"space": "my_space", "externalId": "MyContainer"},
                "containerPropertyIdentifier": "name",
                "type": {"type": "text"},
                "constraintState": {"nullability": "current"},
            },
            "anEdge": {
                "connectionType": "multi_edge_connection",
                "type": {
                    "space": "my_space",
                    "externalId": "MyEdgeType",
                },
                "source": {"space": "my_space", "externalId": "MyTargetType", "version": "v1", "type": "view"},
            },
        },
        createdTime=0,
        lastUpdatedTime=1,
        writable=True,
        queryable=True,
        usedFor="node",
        isGlobal=False,
        mappedContainers=[{"space": "my_space", "externalId": "MyContainer"}],
    )


@pytest.fixture
def example_dms_container_response() -> dict[str, Any]:
    return dict(
        space="my_space",
        externalId="MyContainer",
        name="My Container",
        description="An example container",
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
    )


@pytest.fixture
def example_dms_space_response() -> dict[str, Any]:
    return dict(
        space="my_space",
        name="My Space",
        description="An example space",
        createdTime=0,
        lastUpdatedTime=1,
        isGlobal=False,
    )


@pytest.fixture
def example_dms_schema_response(
    example_dms_data_model_response: dict[str, Any],
    example_dms_view_response: dict[str, Any],
    example_dms_container_response: dict[str, Any],
    example_dms_space_response: dict[str, Any],
) -> dict[str, Any]:
    return {
        "dataModel": example_dms_data_model_response,
        "views": [example_dms_view_response],
        "containers": [example_dms_container_response],
        "spaces": [example_dms_space_response],
    }


@pytest.fixture
def example_dms_schema_request(
    example_dms_data_model_response: dict[str, Any],
    example_dms_view_response: dict[str, Any],
    example_dms_container_response: dict[str, Any],
    example_dms_space_response: dict[str, Any],
) -> dict[str, Any]:
    return {
        "dataModel": DataModelResponse.model_validate(example_dms_data_model_response)
        .as_request()
        .model_dump(by_alias=True, exclude_unset=True),
        "views": [
            ViewResponse.model_validate(example_dms_view_response)
            .as_request()
            .model_dump(by_alias=True, exclude_unset=True)
        ],
        "containers": [
            ContainerResponse.model_validate(example_dms_container_response)
            .as_request()
            .model_dump(by_alias=True, exclude_unset=True)
        ],
        "spaces": [
            SpaceResponse.model_validate(example_dms_space_response)
            .as_request()
            .model_dump(by_alias=True, exclude_unset=True)
        ],
    }


@pytest.fixture
def respx_mock_data_model(
    neat_client: NeatClient,
    respx_mock: respx.MockRouter,
    example_dms_data_model_response: dict[str, Any],
    example_dms_view_response: dict[str, Any],
    example_dms_container_response: dict[str, Any],
    example_dms_space_response: dict[str, Any],
) -> respx.MockRouter:
    config = neat_client.config

    # Mock data model retrieval
    respx_mock.post(config.create_api_url("/models/datamodels/byids")).respond(
        status_code=200,
        json={"items": [example_dms_data_model_response]},
    )

    # Mock views retrieval
    respx_mock.post(config.create_api_url("/models/views/byids")).respond(
        status_code=200,
        json={"items": [example_dms_view_response]},
    )

    # Mock containers retrieval
    respx_mock.post(config.create_api_url("/models/containers/byids")).respond(
        status_code=200,
        json={"items": [example_dms_container_response]},
    )

    # Mock spaces retrieval
    respx_mock.post(config.create_api_url("/models/spaces/byids")).respond(
        status_code=200,
        json={"items": [example_dms_space_response]},
    )
    return respx_mock
