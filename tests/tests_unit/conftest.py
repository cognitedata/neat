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
