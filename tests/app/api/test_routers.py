import pytest
from cognite.client import CogniteClient
from starlette.testclient import TestClient


from cognite import neat
from cognite.neat.constants import EXAMPLE_WORKFLOWS
from cognite.neat.rules.models import TransformationRules
from cognite.neat.workflows.base import BaseWorkflow
from cognite.neat.workflows.model import WorkflowDefinition
from cognite.neat.app.api.data_classes.rest import RunWorkflowRequest
from tests.app.api.memory_cognite_client import MemoryClient


@pytest.fixture(scope="session")
def workflow_definitions() -> list[WorkflowDefinition]:
    definitions = []
    for example in EXAMPLE_WORKFLOWS.iterdir():
        definition = (example / "workflow.yaml").read_text()
        loaded = BaseWorkflow.deserialize_definition(definition, "yaml")
        definitions.append(loaded)
    return definitions


@pytest.fixture(scope="session")
def workflow_names() -> list[str]:
    return [example.name for example in EXAMPLE_WORKFLOWS.iterdir()]


def test_workflow_workflows(workflow_names: list[str], fastapi_client: TestClient):
    # Act
    response = fastapi_client.get("/api/workflow/workflows")

    # Assert
    result = response.json()
    assert sorted(result["workflows"]) == sorted(workflow_names)


def test_rules(transformation_rules: TransformationRules, fastapi_client: TestClient):
    # transformation_rules load Rules-Nordic44-to-TNT.xlsx
    # /api/rules fetch rules related to default workflow which are Rules-Nordic44-to-TNT.xlsx
    response = fastapi_client.get("/api/rules")

    # Assert
    assert response.status_code == 200
    rules = response.json()
    assert len(transformation_rules.classes) == len(rules["classes"])
    assert len(transformation_rules.properties) == len(rules["properties"])


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy", "sheet2cdf"])
def test_workflow_start(
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
            "/api/workflow/workflow-definition/graph_to_asset_hierarchy", json=definition.model_dump()
        )
        assert response.status_code == 200

    # Act
    response = fastapi_client.post(
        "/api/workflow/start",
        json=RunWorkflowRequest(name=workflow_name, sync=True, config={}, start_step="").model_dump(),
    )

    print(response.json()["result"])

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["is_success"]
    data = {}
    for resource_name in ["assets", "relationships", "labels"]:
        memory: MemoryClient = getattr(cognite_client, resource_name)
        data[resource_name] = memory.dump(ordered=True, exclude={"metadata.start_time", "metadata.update_time"})
    data_regression.check(data, basename=f"{workflow_name}_workflow")


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy", "sheet2cdf"])
def test_workflow_stats(
    workflow_name: str,
    fastapi_client: TestClient,
):
    # Act
    response = fastapi_client.get(
        f"/api/workflow/stats/{workflow_name}",
    )

    assert response.status_code == 200
    assert response.json()["workflow_name"] == workflow_name
    assert response.json()["state"] == "CREATED"


def test_workflow_reload_workflows(
    workflow_names: list[str],
    fastapi_client: TestClient,
):
    # Act
    response = fastapi_client.post(
        "/api/workflow/reload-workflows",
    )

    assert response.status_code == 200
    assert response.json()["result"] == "ok"
    assert sorted(response.json()["workflows"]) == sorted(workflow_names)


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy", "sheet2cdf"])
def test_workflow_workflow_definition_get(
    workflow_name: str,
    fastapi_client: TestClient,
):
    # Act
    response = fastapi_client.get(
        f"/api/workflow/workflow-definition/{workflow_name}",
    )

    assert response.status_code == 200
    assert response.json()["definition"]["name"] == workflow_name


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy", "sheet2cdf"])
def test_workflow_workflow_definition_post(
    workflow_name: str,
    fastapi_client: TestClient,
):
    # Act
    response = fastapi_client.post(
        f"/api/workflow/workflow-definition/{workflow_name}",
    )

    assert response.status_code == 200
    assert response.json()["definition"]["name"] == workflow_name


def test_about(
    fastapi_client: TestClient,
):
    # Act
    response = fastapi_client.get(
        "/api/about",
    )

    assert response.status_code == 200
    assert response.json()["version"] == neat.__version__


def test_configs_global(
    fastapi_client: TestClient,
):
    # Act
    response = fastapi_client.get(
        "/api/configs/global",
    )

    assert response.status_code == 200
    assert response.json()["log_level"] == "INFO"
    assert response.json()["workflows_store_type"] == "file"
