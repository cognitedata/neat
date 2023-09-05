from pathlib import Path
from urllib.parse import quote

import pytest
from cognite.client import CogniteClient
from starlette.testclient import TestClient

from cognite import neat
from cognite.neat.app.api.configuration import neat_app
from cognite.neat.app.api.data_classes.rest import QueryRequest, RuleRequest, RunWorkflowRequest
from cognite.neat.app.api.utils.query_templates import query_templates
from cognite.neat.constants import EXAMPLE_WORKFLOWS
from cognite.neat.rules.models import TransformationRules
from cognite.neat.workflows.base import BaseWorkflow
from cognite.neat.workflows.model import WorkflowConfigItem, WorkflowDefinition
from tests.app.api.memory_cognite_client import MemoryClient


@pytest.fixture(scope="session")
def workflow_directories() -> list[Path]:
    return [
        example
        for example in EXAMPLE_WORKFLOWS.iterdir()
        if not example.name.startswith(".") and not example.name.startswith("_")
    ]


@pytest.fixture(scope="session")
def workflow_definitions(workflow_directories: list[Path]) -> list[WorkflowDefinition]:
    definitions = []
    for example in workflow_directories:
        definition = (example / "workflow.yaml").read_text()
        loaded = BaseWorkflow.deserialize_definition(definition, "yaml")
        definitions.append(loaded)
    return definitions


@pytest.fixture(scope="session")
def workflow_names(workflow_directories: list[Path]) -> list[str]:
    return [example.name for example in workflow_directories]


def test_workflow_workflows(workflow_names: list[str], fastapi_client: TestClient):
    # Act
    response = fastapi_client.get("/api/workflow/workflows")

    # Assert
    result = response.json()
    assert sorted(result["workflows"]) == sorted(workflow_names)


def test_rules(transformation_rules: TransformationRules, fastapi_client: TestClient):
    # transformation_rules load Rules-Nordic44-to-TNT.xlsx
    # /api/rules fetch rules related to default workflow which are Rules-Nordic44-to-TNT.xlsx
    response = fastapi_client.get("/api/rules", params={"workflow_name": "graph_to_asset_hierarchy"})

    # Assert
    assert response.status_code == 200
    rules = response.json()
    assert len(transformation_rules.classes) == len(rules["classes"])
    assert len(transformation_rules.properties) == len(rules["properties"])


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy"])
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


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy"])
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
    assert response.json()["state"] == "COMPLETED"


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


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy"])
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


def test_list_queries(
    fastapi_client: TestClient,
):
    # Act
    response = fastapi_client.get(
        "/api/list-queries",
    )

    assert response.status_code == 200
    assert response.json() == query_templates


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy"])
def test_query(
    workflow_name: str,
    fastapi_client: TestClient,
):
    # Act
    workflow = neat_app.workflow_manager.get_workflow(workflow_name)
    configs = workflow.get_configs()
    configs.set_config_item(WorkflowConfigItem(name="source_rdf_store.type", value="memory"))
    configs.set_config_item(WorkflowConfigItem(name="solution_rdf_store.type", value="memory"))
    workflow.enable_step("step_generate_assets", False)
    neat_app.workflow_manager.start_workflow_instance(workflow_name, sync=True)

    response = fastapi_client.post(
        "/api/query",
        json=QueryRequest(
            graph_name="source", workflow_name=workflow_name, query="SELECT DISTINCT ?class WHERE { ?s a ?class }"
        ).model_dump(),
    )

    content = response.json()

    assert response.status_code == 200
    assert content, "Missing content"
    assert content["fields"] == ["class"], f"Missing fields, got {content}"
    assert len(content["rows"]) == 59
    assert len(content["rows"]) == 59
    assert {"class": "http://iec.ch/TC57/2013/CIM-schema-cim16#Terminal"} in content["rows"]


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy"])
def test_execute_rule(
    workflow_name: str,
    fastapi_client: TestClient,
):
    # Act
    workflow = neat_app.workflow_manager.get_workflow(workflow_name)
    if "SourceGraph" not in workflow.get_context():
        workflow.enable_step("step_generate_assets", False)
        neat_app.workflow_manager.start_workflow_instance(workflow_name, sync=True)

    response = fastapi_client.post(
        "/api/execute-rule",
        json=RuleRequest(
            graph_name="source",
            workflow_name=workflow_name,
            rule_type="rdfpath",
            rule="cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation",
        ).model_dump(),
    )

    content = response.json()

    assert response.status_code == 200
    assert content["fields"] == ["subject", "predicate", "object"]
    assert {
        "subject": "http://purl.org/cognite/neat#_2dd901ff-bdfb-11e5-94fa-c8f73332c8f4",
        "predicate": "http://purl.org/dc/terms/relation",
        "object": "http://purl.org/cognite/neat#_f176965a-9aeb-11e5-91da-b8763fd99c5f",
    } in content["rows"]


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy"])
def test_object_properties(
    workflow_name: str,
    fastapi_client: TestClient,
):
    reference = quote("http://purl.org/cognite/neat#_lazarevac")
    graph_name = "source"

    # Act
    response = fastapi_client.get(
        f"/api/object-properties?reference={reference}&graph_name={graph_name}&workflow_name={workflow_name}",
    )

    content = response.json()

    assert response.status_code == 200
    assert content["fields"] == ["property", "value"]
    assert {
        "property": "http://iec.ch/TC57/2013/CIM-schema-cim16#IdentifiedObject.description",
        "value": "Serbia",
    } in content["rows"]


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy"])
def test_search(
    workflow_name: str,
    fastapi_client: TestClient,
):
    search_str = "Serbia"
    graph_name = "source"
    search_type = "value_exact_match"

    # Act
    response = fastapi_client.get(
        f"/api/search?search_str={search_str}&graph_name={graph_name}&search_type={search_type}&workflow_name={workflow_name}",
    )

    content = response.json()

    assert response.status_code == 200
    assert content["fields"] == ["object_ref", "type", "property", "value"]
    assert {
        "object_ref": "http://purl.org/cognite/neat#_lazarevac",
        "type": "http://iec.ch/TC57/2013/CIM-schema-cim16#GeographicalRegion",
        "property": "http://iec.ch/TC57/2013/CIM-schema-cim16#IdentifiedObject.description",
        "value": "Serbia",
    } in content["rows"]


@pytest.mark.parametrize("workflow_name", ["graph_to_asset_hierarchy"])
def test_get_classes(
    workflow_name: str,
    fastapi_client: TestClient,
):
    # Act
    response = fastapi_client.get(
        f"/api/get-classes?graph_name=source&workflow_name={workflow_name}&cache=true",
    )

    content = response.json()

    assert response.status_code == 200
    assert content["fields"] == ["class", "instances"]
    assert {"class": "http://iec.ch/TC57/2013/CIM-schema-cim16#Substation", "instances": "44"} in content["rows"]
    assert len(content["rows"]) == 59
