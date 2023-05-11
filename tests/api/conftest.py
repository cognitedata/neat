import pytest
from fastapi.testclient import TestClient

from cognite.neat.explorer.explorer import app
from tests.api.memory_cognite_client import memory_cognite_client


@pytest.fixture(scope="function")
def cognite_client():
    with memory_cognite_client() as client:
        yield client


@pytest.fixture(scope="function")
def fastapi_client(cognite_client):
    with TestClient(app) as test_client:
        yield test_client
