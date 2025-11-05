import os

import pytest
from cognite.client import ClientConfig
from cognite.client.credentials import OAuthClientCredentials, Token
from dotenv import load_dotenv

from cognite.neat._client import NeatClient
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
            credentials=OAuthClientCredentials.default_for_azure_ad(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                cdf_cluster=cluster,
            ),
        )
    )
