import gzip
import json
from collections import Counter
from typing import Any
from unittest.mock import patch

import pytest
import respx

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer._differ_container import ContainerDiffer
from cognite.neat._data_model.deployer.data_classes import (
    AddedField,
    ChangedField,
    ContainerDeploymentPlan,
    RemovedField,
    ResourceChange,
    ResourceDeploymentPlan,
    SchemaSnapshot,
    SeverityType,
)
from cognite.neat._data_model.deployer.deployer import DeploymentOptions, SchemaDeployer
from cognite.neat._data_model.models.dms import (
    BtreeIndex,
    ContainerConstraintReference,
    ContainerIndexReference,
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    RequestSchema,
    RequiresConstraintDefinition,
    TextProperty,
    UniquenessConstraintDefinition,
)


@pytest.fixture()
def model(example_dms_schema_response: dict[str, Any]) -> RequestSchema:
    return RequestSchema.model_validate(example_dms_schema_response)


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

    def test_create_deployment_plan_container_different_space(
        self, neat_client: NeatClient, model: RequestSchema, schema_snapshot: SchemaSnapshot
    ) -> None:
        assert len(model.containers) > 0, "Model must have at least one container for this test"
        new_container = model.containers[0].model_copy(update={"space": "different_space"}, deep=True)
        modified_model = model.model_copy(update={"containers": [new_container] + model.containers[1:]}, deep=True)
        deployer = SchemaDeployer(neat_client)
        plan = deployer.create_deployment_plan(schema_snapshot, modified_model)
        assert len(plan) == 4  # spaces, containers, views, datamodels
        for resource_plan in plan:
            assert resource_plan.endpoint in {"spaces", "containers", "views", "datamodels"}
            if resource_plan.endpoint == "containers":
                assert len(resource_plan.skip) == 1, "Container with different space should be skipped"

    def test_creat_deployment_plan_container_index_constraint_changes(
        self, neat_client: NeatClient, model: RequestSchema, schema_snapshot: SchemaSnapshot
    ) -> None:
        assert len(schema_snapshot.containers) > 0, "Model must have at least one container for this test"

        # Add an index and a constraint to the current container in the snapshot
        current_container = next(iter(schema_snapshot.containers.values()))
        prop_id, prop = next(iter(current_container.properties.items()))
        constraint_id = "unique_constraint_1"
        constraint = UniquenessConstraintDefinition(properties=[prop_id], bySpace=False)
        current_container.constraints = {constraint_id: constraint, **(current_container.constraints or {})}
        index_id = "btree_index_1"
        index = BtreeIndex(properties=[prop_id], bySpace=False)
        current_container.indexes = {index_id: index, **(current_container.indexes or {})}
        schema_snapshot.containers[current_container.as_reference()] = current_container

        # Modify the model to have the index and constraint modified by setting by_space=True
        modified_container = current_container.model_copy(
            deep=True,
            update={
                "indexes": {
                    **(current_container.indexes or {}),
                    index_id: BtreeIndex(properties=[prop_id], bySpace=True),
                },
                "constraints": {
                    **(current_container.constraints or {}),
                    constraint_id: UniquenessConstraintDefinition(properties=[prop_id], bySpace=True),
                },
            },
        )
        model.containers = [
            modified_container if container.as_reference() == modified_container.as_reference() else container
            for container in model.containers
        ]

        deployer = SchemaDeployer(neat_client)
        plan = deployer.create_deployment_plan(schema_snapshot, model)

        container_plan = next(rp for rp in plan if rp.endpoint == "containers")
        assert len(container_plan.resources) == 1
        assert isinstance(container_plan, ContainerDeploymentPlan)
        assert len(container_plan.indexes_to_remove) == 1
        assert len(container_plan.constraints_to_remove) == 1
        resource_plan = next(
            (change for change in container_plan.resources if change.resource_id == modified_container.as_reference()),
            None,
        )
        assert resource_plan is not None
        change_types = Counter(
            type(change)
            for change in resource_plan.changes
            if change.field_path.startswith("indexes.") or change.field_path.startswith("constraints.")
        )
        assert change_types == {
            # One for index, one for constraint
            RemovedField: 2,  # type: ignore[dict-item]
            AddedField: 2,
        }

    def test_deploy_dry_run(
        self, neat_client: NeatClient, model: RequestSchema, respx_mock_data_model: respx.MockRouter
    ) -> None:
        deployer = SchemaDeployer(neat_client, options=DeploymentOptions(dry_run=True))
        deployer.run(model)
        result = deployer.result
        assert result.is_dry_run
        assert result.status == "pending"
        assert result.is_success
        assert result.responses is None

    def test_apply_plan(self, neat_client: NeatClient, model: RequestSchema, respx_mock: respx.MockRouter) -> None:
        deployer = SchemaDeployer(neat_client, options=DeploymentOptions(dry_run=False))
        plan: list[ResourceDeploymentPlan] = [
            ResourceDeploymentPlan(
                endpoint="spaces",
                resources=[ResourceChange(resource_id=space.as_reference(), new_value=space) for space in model.spaces],
            ),
            ResourceDeploymentPlan(
                endpoint="containers",
                resources=[
                    ResourceChange(resource_id=container.as_reference(), new_value=container)
                    for container in model.containers
                ],
            ),
            ResourceDeploymentPlan(
                endpoint="views",
                resources=[
                    ResourceChange(
                        resource_id=view.as_reference(),
                        new_value=view,
                        current_value=view.model_copy(update={"name": "old name"}, deep=True),
                        changes=[
                            ChangedField(
                                field_path="name",
                                item_severity=SeverityType.SAFE,
                                new_value=view.name,
                                current_value="old name",
                            )
                        ],
                    )
                    for view in model.views
                ],
            ),
            ResourceDeploymentPlan(
                endpoint="datamodels",
                resources=[
                    ResourceChange(
                        resource_id=model.data_model.as_reference(), new_value=None, current_value=model.data_model
                    ),  # Trigger delete.
                    ResourceChange(resource_id=model.data_model.as_reference(), new_value=model.data_model),
                ],
            ),
        ]
        # Mock the responses for creation/update (same endpoint in data modeling API)
        for resource_plan in plan:
            respx_mock.post(neat_client.config.create_api_url(f"/models/{resource_plan.endpoint}")).respond(
                status_code=200,
                json={
                    "items": [
                        change.new_value.model_dump(by_alias=True)
                        for change in resource_plan.to_upsert
                        if change.new_value is not None
                    ]
                },
            )
            if resource_plan.endpoint == "datamodels":
                # Mock delete endpoint
                respx_mock.post(neat_client.config.create_api_url(f"/models/{resource_plan.endpoint}/delete")).respond(
                    status_code=200,
                    json={
                        "items": [
                            change.current_value.model_dump(by_alias=True)
                            for change in resource_plan.to_delete
                            if change.current_value is not None
                        ]
                    },
                )

        with patch("time.sleep"):  # In order to speed up tests
            result = deployer.apply_changes(plan)

        assert result.is_success
        created_resources = len(result.created)
        expected_created = len(model.spaces) + len(model.containers) + 1  # +1 for datamodel
        assert created_resources == expected_created
        assert len(result.updated) == len(model.views)  # All views updated
        assert len(result.deletions) == 1  # One datamodel deleted
        assert len(result.unchanged) == 0

    def test_apply_plan_remove_indexes_and_constraints(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter
    ) -> None:
        current_container = ContainerRequest(
            space="space1",
            externalId="container1",
            name="container1",
            properties={"prop1": ContainerPropertyDefinition(type=TextProperty())},
            constraints={
                "constraint1": RequiresConstraintDefinition(
                    require=ContainerReference(space="space1", external_id="container2")
                )
            },
            indexes={"index1": BtreeIndex(properties=["prop1"])},
        )
        new_container = current_container.model_copy(update={"constraints": {}, "indexes": {}}, deep=True)
        changes = ContainerDiffer().diff(current_container, new_container)
        plan: list[ResourceDeploymentPlan] = [
            ContainerDeploymentPlan(
                resources=[
                    ResourceChange(
                        resource_id=current_container.as_reference(),
                        new_value=new_container,
                        current_value=current_container,
                        changes=changes,
                    )
                ],
            )
        ]
        config = neat_client.config
        respx_mock.post(config.create_api_url("/models/containers/constraints/delete")).respond(status_code=200)
        respx_mock.post(config.create_api_url("/models/containers/indexes/delete")).respond(status_code=200)

        deployer = SchemaDeployer(neat_client, options=DeploymentOptions(dry_run=False))
        with patch("time.sleep"):  # In order to speed up tests
            result = deployer.apply_changes(plan)

        assert len(result.changed_fields) == 2  # One for index removal, one for constraint removal
        removed_index = next(
            (
                field
                for field in result.changed_fields
                if isinstance(field.field_change, RemovedField) and field.field_change.field_path.startswith("indexes.")
            ),
            None,
        )
        assert removed_index is not None
        assert removed_index.message.ids == [
            ContainerIndexReference(space="space1", external_id="container1", identifier="index1")
        ]
        removed_constriant = next(
            (
                field
                for field in result.changed_fields
                if isinstance(field.field_change, RemovedField)
                and field.field_change.field_path.startswith("constraints.")
            ),
            None,
        )
        assert removed_constriant is not None
        assert removed_constriant.message.ids == [
            ContainerConstraintReference(space="space1", external_id="container1", identifier="constraint1")
        ]

        # Assert the correct requests were made
        assert respx_mock.calls.call_count == 2
        constraint_request = respx_mock.calls[0].request
        assert constraint_request.content.startswith(b"\x1f\x8b"), "Expected gzip compressed content"
        constraint_request = gzip.decompress(constraint_request.content).decode("utf-8")
        assert json.loads(constraint_request) == {
            "items": [{"space": "space1", "externalId": "container1", "identifier": "constraint1"}]
        }
        index_request = respx_mock.calls[1].request
        assert index_request.content.startswith(b"\x1f\x8b"), "Expected gzip compressed content"
        index_request = gzip.decompress(index_request.content).decode("utf-8")
        assert json.loads(index_request) == {
            "items": [{"space": "space1", "externalId": "container1", "identifier": "index1"}]
        }

        # There should be no created, updated, unchanged, or deleted resources
        assert len(result.created) == 0
        assert len(result.unchanged) == 0
        assert len(result.updated) == 0
        assert len(result.deletions) == 0

        # All requests should be successful
        assert result.is_success
