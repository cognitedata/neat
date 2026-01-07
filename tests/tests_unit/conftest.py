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
        filter={
            "and": [
                {"hasData": [{"space": "my_space", "externalId": "MyView", "type": "container"}]},
                {"exists": {"property": ["node", "externalId"]}},
            ]
        },
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
