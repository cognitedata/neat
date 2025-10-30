from typing import Any

import pytest
import respx

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer import DeploymentOptions, SchemaDeployer
from cognite.neat._data_model.deployer.data_classes import SchemaSnapshot
from cognite.neat._data_model.models.dms import RequestSchema


@pytest.fixture()
def model(example_dms_schema: dict[str, Any]) -> RequestSchema:
    return RequestSchema.model_validate(example_dms_schema)


@pytest.fixture()
def schema_snapshot(
    neat_client: NeatClient, model: RequestSchema, respx_mock_data_model: respx.MockRouter
) -> SchemaSnapshot:
    deployer = SchemaDeployer(client=neat_client)
    return deployer.fetch_cdf_state(model)


class TestSchemaDeployer:
    def test_fetch_existing_schemas(
        self, neat_client: NeatClient, model: RequestSchema, schema_snapshot: SchemaSnapshot
    ) -> None:
        cdf_schema = schema_snapshot
        assert set(cdf_schema.data_model) == {model.data_model.as_reference()}
        assert set(cdf_schema.views) == {view.as_reference() for view in model.views}
        assert set(cdf_schema.spaces) == {space.as_reference() for space in model.spaces}
        assert set(cdf_schema.containers) == {container.as_reference() for container in model.containers}

    def test_create_deployment_plan(
        self, neat_client: NeatClient, model: RequestSchema, schema_snapshot: SchemaSnapshot
    ) -> None:
        deployer = SchemaDeployer(neat_client)
        plan = deployer.create_deployment_plan(schema_snapshot, model)
        # Basic assertions to ensure plan is created
        assert len(plan) == 4  # spaces, containers, views, datamodels
        for resource_plan in plan:
            assert resource_plan.endpoint in {"spaces", "containers", "views", "datamodels"}
            assert len(resource_plan.unchanged) == len(resource_plan.resources), (
                "All resources should be unchanged as we use the same new as current model"
            )

    def test_deploy_dry_run(
        self, neat_client: NeatClient, model: RequestSchema, respx_mock_data_model: respx.MockRouter
    ) -> None:
        deployer = SchemaDeployer(neat_client, options=DeploymentOptions(dry_run=True))
        deployer.run(model)
        result = deployer.results
        assert result.is_dry_run
        assert result.status == "pending"
        assert result.is_success
        assert result.responses is None

    def test_deploy(
        self, neat_client: NeatClient, model: RequestSchema, respx_mock_data_model: respx.MockRouter
    ) -> None:
        deployer = SchemaDeployer(neat_client, options=DeploymentOptions(dry_run=False))
        with pytest.raises(NotImplementedError):
            deployer.deploy(model)
