import pytest
from cognite.client import CogniteClient
from starlette.testclient import TestClient

from cognite.neat.constants import EXAMPLE_WORKFLOWS
from cognite.neat.core.rules.models import TransformationRules
from cognite.neat.core.workflow import BaseWorkflow
from cognite.neat.core.workflow.model import WorkflowDefinition
from cognite.neat.explorer.data_classes.rest import RunWorkflowRequest
from tests.api.memory_cognite_client import MemoryClient


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


def test_load_rules(transformation_rules: TransformationRules, fastapi_client: TestClient):
    response = fastapi_client.get("/api/rules")

    # Assert
    assert response.status_code == 200
    rules = response.json()
    assert len(transformation_rules.classes) == len(rules["classes"])
    assert len(transformation_rules.properties) == len(rules["properties"])


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy", "sheet2cdf"])
def test_run_default_workflow(
    workflow_name: str,
    cognite_client: CogniteClient,
    fastapi_client: TestClient,
    data_regression,
    tmp_path,
):
    # Arrange
    if workflow_name == "graph_to_asset_hierarchy":
        # When running this test in GitHub actions, you get permission issues with the default disk_store_dir.
        response = fastapi_client.get("/api/workflow/workflow-definition/graph_to_asset_hierarchy")
        definition = WorkflowDefinition(**response.json()["definition"])
        response = fastapi_client.post(
            "/api/workflow/workflow-definition/graph_to_asset_hierarchy", json=definition.dict()
        )
        assert response.status_code == 200

    # Act
    response = fastapi_client.post(
        "/api/workflow/start",
        json=RunWorkflowRequest(name=workflow_name, sync=True, config={}, start_step="").dict(),
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["is_success"]
    data = {}
    for resource_name in ["assets", "relationships", "labels"]:
        memory: MemoryClient = getattr(cognite_client, resource_name)
        data[resource_name] = memory.dump(ordered=True, exclude={"metadata.start_time", "metadata.update_time"})
    data_regression.check(data, basename=f"{workflow_name}_workflow")
