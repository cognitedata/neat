from typing import Any

import pytest
from cognite.client import ClientConfig
from cognite.client.credentials import Token

from cognite.neat._client import NeatClient, NeatClientConfig

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
        description="An example view",
        properties={
            "name": {
                "container": {"space": "my_space", "externalId": "MyContainer"},
                "containerPropertyIdentifier": "name",
                "type": {"type": "text"},
                "connectionType": "primary_property",
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
def example_dms_schema(
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
