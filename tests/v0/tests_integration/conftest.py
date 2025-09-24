import os

import pytest
from cognite.client import CogniteClient
from dotenv import load_dotenv

from cognite.neat.v0.core._client import NeatClient
from tests.v0.config import ROOT


@pytest.fixture(scope="session")
def cognite_client() -> CogniteClient:
    load_dotenv(ROOT / ".env", override=True)

    try:
        cluster = os.environ["CDF_CLUSTER"]
        project = os.environ["CDF_PROJECT"]
        tenant_id = os.environ["IDP_TENANT_ID"]
        client_id = os.environ["IDP_CLIENT_ID"]
        client_secret = os.environ["IDP_CLIENT_SECRET"]
    except KeyError:
        pytest.skip("Environment variables missing, skipping integration tests")

    return CogniteClient.default_oauth_client_credentials(
        cdf_cluster=cluster, project=project, tenant_id=tenant_id, client_id=client_id, client_secret=client_secret
    )


@pytest.fixture(scope="session")
def neat_client(cognite_client: CogniteClient) -> NeatClient:
    return NeatClient(cognite_client)
