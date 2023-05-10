import pytest
from cognite.client.testing import monkeypatch_cognite_client
from fastapi.testclient import TestClient

from cognite.neat.explorer.explorer import app


@pytest.fixture(scope="session")
def cognite_client():
    with monkeypatch_cognite_client() as client:
        yield client


@pytest.fixture(scope="session")
def fastapi_client(cognite_client):
    with TestClient(app) as test_client:
        yield test_client
