import pytest
from fastapi.testclient import TestClient

from cognite.neat.app.api.explorer import app
from tests.tests_units.app.api.memory_cognite_client import memory_cognite_client


@pytest.fixture(scope="session")
def cognite_client():
    with memory_cognite_client() as client:
        yield client


@pytest.fixture(scope="session")
def fastapi_client(cognite_client):
    with TestClient(app) as test_client:
        yield test_client
