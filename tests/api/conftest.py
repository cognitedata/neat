import pytest
from fastapi.testclient import TestClient

from cognite.neat.explorer.explorer import app


@pytest.fixture(scope="session")
def fastapi_client():
    return TestClient(app)
