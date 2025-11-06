import os

import pytest
from cognite.client import ClientConfig
from cognite.client.credentials import OAuthClientCredentials, Token
from dotenv import load_dotenv

from cognite.neat._client import NeatClient
from cognite.neat._data_model.models.dms import SpaceRequest, SpaceResponse
from cognite.neat._utils.http_client import ParametersRequest, ResponseMessage
from tests.config import ROOT


@pytest.fixture(scope="session")
def neat_client() -> NeatClient:
    load_dotenv(ROOT / ".env", override=True)

    try:
        cluster = os.environ["CDF_CLUSTER"]
        project = os.environ["CDF_PROJECT"]
        tenant_id = os.environ["IDP_TENANT_ID"]
        client_id = os.environ["IDP_CLIENT_ID"]
        client_secret = os.environ["IDP_CLIENT_SECRET"]
    except KeyError:
        pytest.skip("Environment variables missing, skipping integration tests")
        # Just to make mypy happy, pytest will never return from skip()
        return NeatClient(ClientConfig("this will never happen", project="invalid", credentials=Token("not-used")))

    return NeatClient(
        ClientConfig(
            client_name="neat_integration_tests",
            project=project,
            base_url=f"https://{cluster}.cognitedata.com",
            credentials=OAuthClientCredentials.default_for_azure_ad(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                cdf_cluster=cluster,
            ),
        )
    )


@pytest.fixture(scope="session")
def neat_test_space(neat_client: NeatClient) -> SpaceResponse:
    """This is the default test space for NEAT integration tests.

    It is created once and should never be deleted.
    """
    space_req = SpaceRequest(
        space="neat_integration_test_space",
        name="Neat Integration Test Space",
        description="Space for NEAT integration tests",
    )
    space_response_list = neat_client.spaces.apply([space_req])
    assert len(space_response_list) == 1
    space_response = space_response_list[0]
    return space_response


def test_assert_neat_client(neat_client: NeatClient) -> None:
    assert isinstance(neat_client, NeatClient)
    config = neat_client.config
    url = f"https://{config.cdf_cluster}.cognitedata.com/api/v1/token/inspect"
    responses = neat_client.http_client.request(ParametersRequest(endpoint_url=url, method="GET"))
    assert len(responses) == 1
    response = responses[0]
    assert isinstance(response, ResponseMessage)
    assert response.code == 200
