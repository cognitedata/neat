import pytest
from starlette.testclient import TestClient

from cognite.neat.constants import EXAMPLE_WORKFLOWS
from cognite.neat.core.workflow import BaseWorkflow
from cognite.neat.core.workflow.model import WorkflowDefinition


@pytest.fixture(scope="session")
def workflow_definitions() -> list[WorkflowDefinition]:
    definitions = []
    for example in EXAMPLE_WORKFLOWS.iterdir():
        definition = (example / "workflow.yaml").read_text()
        loaded = BaseWorkflow.deserialize_metadata(definition, "yaml")
        definitions.append(loaded)
    return definitions


@pytest.fixture(scope="session")
def workflow_names() -> list[str]:
    return [example.name for example in EXAMPLE_WORKFLOWS.iterdir()]


def test_load_example_workflows_loaded(workflow_names: list[str], fastapi_client: TestClient):
    # Act
    response = fastapi_client.get("/api/workflow/workflows")

    # Assert
    result = response.json()
    assert sorted(result["workflows"]) == sorted(workflow_names)


def test_load_rules(transformation_rules, fastapi_client: TestClient):
    response = fastapi_client.get("/api/rules")

    # Assert
    assert response.status_code == 200
    rules = response.json()
    assert len(transformation_rules.classes) == len(rules["classes"])
    assert len(transformation_rules.properties) == len(rules["properties"])
