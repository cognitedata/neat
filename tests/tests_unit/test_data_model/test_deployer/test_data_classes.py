from datetime import datetime, timezone

import pytest

from cognite.neat._data_model.deployer._differ_container import ContainerDiffer
from cognite.neat._data_model.deployer._differ_data_model import DataModelDiffer
from cognite.neat._data_model.deployer._differ_view import ViewDiffer
from cognite.neat._data_model.deployer.data_classes import (
    AppliedChanges,
    ChangeResult,
    ContainerDeploymentPlan,
    DeploymentResult,
    ResourceChange,
    ResourceDeploymentPlan,
    ResourceDeploymentPlanList,
    SchemaSnapshot,
    SeverityType,
)
from cognite.neat._data_model.deployer.deployer import SchemaDeployer
from cognite.neat._data_model.models.dms import (
    BtreeIndex,
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelRequest,
    RequiresConstraintDefinition,
    TextProperty,
    ViewCorePropertyRequest,
    ViewRequest,
)
from cognite.neat._utils.http_client import SuccessResponseItems


class TestSeverityType:
    @pytest.mark.parametrize(
        "severities,expected_max",
        [
            pytest.param(
                [SeverityType.SAFE, SeverityType.WARNING, SeverityType.BREAKING],
                SeverityType.BREAKING,
                id="max is BREAKING",
            ),
            pytest.param(
                [SeverityType.SAFE, SeverityType.WARNING],
                SeverityType.WARNING,
                id="max is WARNING",
            ),
            pytest.param(
                [SeverityType.SAFE],
                SeverityType.SAFE,
                id="max is SAFE",
            ),
            pytest.param(
                [],
                SeverityType.SAFE,
                id="empty list returns default",
            ),
        ],
    )
    def test_max_severity(self, severities: list[SeverityType], expected_max: SeverityType) -> None:
        result = SeverityType.max_severity(severities, default=SeverityType.SAFE)
        assert result == expected_max


@pytest.fixture
def plan_with_removals() -> ResourceDeploymentPlanList:
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
    new_container = current_container.model_copy(update={"constraints": {}, "indexes": {}, "properties": {}})
    current_view = ViewRequest(
        space="space1",
        externalId="view1",
        version="v1",
        properties={
            "prop1": ViewCorePropertyRequest(
                container=current_container.as_reference(), containerPropertyIdentifier="prop1"
            )
        },
    )
    new_view = current_view.model_copy(update={"properties": {}})
    model = DataModelRequest(space="space1", externalId="model1", version="v1", views=[current_view.as_reference()])
    new_model = model.model_copy(update={"views": []}, deep=True)

    return ResourceDeploymentPlanList(
        [
            ResourceDeploymentPlan(
                endpoint="containers",
                resources=[
                    ResourceChange(
                        resource_id=current_container.as_reference(),
                        new_value=new_container,
                        current_value=current_container,
                        changes=ContainerDiffer().diff(current_container, new_container),
                    )
                ],
            ),
            ResourceDeploymentPlan(
                endpoint="views",
                resources=[
                    ResourceChange(
                        resource_id=current_view.as_reference(),
                        new_value=new_view,
                        current_value=current_view,
                        changes=ViewDiffer(
                            current_container_map={current_container.as_reference(): current_container},
                            new_container_map={new_container.as_reference(): new_container},
                        ).diff(current_view, new_view),
                    )
                ],
            ),
            ResourceDeploymentPlan(
                endpoint="datamodels",
                resources=[
                    ResourceChange(
                        resource_id=model.as_reference(),
                        new_value=new_model,
                        current_value=model,
                        changes=DataModelDiffer().diff(model, new_model),
                    )
                ],
            ),
        ]
    )


class TestResourceDeploymentPlanList:
    def test_consolidate_resources(self, plan_with_removals: ResourceDeploymentPlanList) -> None:
        plan = plan_with_removals

        consolidated_plan = plan.consolidate_changes()

        assert len(consolidated_plan) == 3
        for resource_plan in consolidated_plan.data:
            # All removed properties, constraints, indexes, and views should lead to unchanged resources
            assert len(resource_plan.unchanged) == 1
            assert len(resource_plan.to_create) == 0
            assert len(resource_plan.to_update) == 0
            assert len(resource_plan.to_delete) == 0

    def test_consolidate_container_index_modifications(self) -> None:
        current_container = ContainerRequest(
            space="space1",
            externalId="container1",
            name="container1",
            properties={"prop1": ContainerPropertyDefinition(type=TextProperty())},
            indexes={
                "index1": BtreeIndex(properties=["prop1"], bySpace=True),
            },
        )
        new_container = current_container.model_copy(
            update={"indexes": {"index1": BtreeIndex(properties=["prop1"], bySpace=False)}}
        )
        changes = SchemaDeployer.remove_readd_modified_indexes_and_constraints(
            ContainerDiffer().diff(current_container, new_container), current_container, new_container
        )

        plan = ResourceDeploymentPlanList(
            [
                ContainerDeploymentPlan(
                    endpoint="containers",
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
        )

        consolidated_plan = plan.consolidate_changes()

        assert len(consolidated_plan) == 1
        resource_plan = consolidated_plan.data[0]
        assert isinstance(resource_plan, ContainerDeploymentPlan)
        assert len(resource_plan.to_update) == 1
        assert len(resource_plan.to_create) == 0
        assert len(resource_plan.unchanged) == 0
        assert len(resource_plan.to_delete) == 0
        assert len(resource_plan.indexes_to_remove) == 1, (
            "Index removal should not be consolidated as it is removed and re-added"
        )

    def test_force_changes_not_drop_data(self, plan_with_removals: ResourceDeploymentPlanList) -> None:
        plan = plan_with_removals

        forced_plan = plan.force_changes(drop_data=False)

        assert len(forced_plan) == 3
        for resource_plan in forced_plan.data:
            if resource_plan.endpoint in ("views", "datamodels"):
                # Views and data models should be recreated
                assert len(resource_plan.unchanged) == 0
                assert len(resource_plan.to_create) == 1
                assert len(resource_plan.to_update) == 0
                assert len(resource_plan.to_delete) == 1
            elif resource_plan.endpoint == "containers":
                # Containers should be unchanged as we do not drop data
                assert len(resource_plan.unchanged) == 1
                assert len(resource_plan.to_create) == 0
                assert len(resource_plan.to_update) == 0
                assert len(resource_plan.to_delete) == 0
            else:
                pytest.fail(f"Unexpected endpoint: {resource_plan.endpoint}")

    def test_force_changes_drop_data(self, plan_with_removals: ResourceDeploymentPlanList) -> None:
        plan = plan_with_removals

        forced_plan = plan.force_changes(drop_data=True)

        assert len(forced_plan) == 3
        for resource_plan in forced_plan.data:
            # All resources should be recreated
            assert len(resource_plan.unchanged) == 0
            assert len(resource_plan.to_create) == 1
            assert len(resource_plan.to_update) == 0
            assert len(resource_plan.to_delete) == 1


class TestAppliedChanges:
    def test_as_recovery_plan(self) -> None:
        container1 = ContainerRequest(
            space="space1",
            externalId="container1",
            name="container1",
            properties={"prop1": ContainerPropertyDefinition(type=TextProperty())},
        )
        container2 = ContainerRequest(
            space="space1",
            externalId="container2",
            name="container2",
            properties={"prop2": ContainerPropertyDefinition(type=TextProperty())},
        )
        container2_update = container2.model_copy(
            update={
                "properties": {
                    "prop2": ContainerPropertyDefinition(type=TextProperty()),
                    "prop2_new": ContainerPropertyDefinition(type=TextProperty()),
                }
            }
        )
        container3 = ContainerRequest(
            space="space1",
            externalId="container3",
            name="container3",
            properties={"prop3": ContainerPropertyDefinition(type=TextProperty())},
        )

        applied_changes = AppliedChanges(
            created=[
                ChangeResult(
                    endpoint="containers",
                    change=ResourceChange(resource_id=container1.as_reference(), new_value=container1),
                    message=SuccessResponseItems(code=200, body="", ids=[container1.as_reference()]),
                )
            ],
            updated=[
                ChangeResult(
                    endpoint="containers",
                    change=ResourceChange(
                        resource_id=container2.as_reference(),
                        current_value=container2,
                        new_value=container2_update,
                        changes=ContainerDiffer().diff(container2, container2_update),
                    ),
                    message=SuccessResponseItems(code=200, body="", ids=[container2.as_reference()]),
                )
            ],
            deletions=[
                ChangeResult(
                    endpoint="containers",
                    change=ResourceChange(
                        resource_id=container3.as_reference(), new_value=None, current_value=container3
                    ),
                    message=SuccessResponseItems(code=200, body="", ids=[container3.as_reference()]),
                )
            ],
        )

        recovery_plan = applied_changes.as_recovery_plan()

        assert len(recovery_plan) == 1
        resource_plan = recovery_plan[0]
        assert resource_plan.endpoint == "containers"
        assert len(resource_plan.to_create) == 1
        assert resource_plan.to_create[0].resource_id == container3.as_reference()
        assert resource_plan.to_create[0].new_value == container3
        assert len(resource_plan.to_update) == 1
        assert resource_plan.to_update[0].resource_id == container2.as_reference()
        assert resource_plan.to_update[0].new_value == container2
        assert len(resource_plan.to_delete) == 1
        assert resource_plan.to_delete[0].resource_id == container1.as_reference()
        assert resource_plan.to_delete[0].current_value == container1


class TestDeploymentResult:
    def test_as_mixpanel_event(self, plan_with_removals: ResourceDeploymentPlanList) -> None:
        plan = plan_with_removals

        deployment_result = DeploymentResult(
            status="success",
            plan=list(plan),
            snapshot=SchemaSnapshot(
                timestamp=datetime.now(tz=timezone.utc),
                data_model={},
                views={},
                containers={},
                spaces={},
                node_types={},
            ),
            responses=AppliedChanges(
                created=[],
                updated=[
                    ChangeResult(
                        endpoint=resource_plan.endpoint,
                        change=resource_change,
                        message=SuccessResponseItems(code=200, body="", ids=[resource_change.resource_id]),
                    )
                    for resource_plan in plan.data
                    for resource_change in resource_plan.resources
                ],
                deletions=[],
                unchanged=[],
                skipped=[],
                changed_fields=[],
            ),
            recovery=None,
        )

        event = deployment_result.as_mixpanel_event()

        assert {
            "containers.update.SuccessResponseItems": 1,
            "datamodels.update.SuccessResponseItems": 1,
            "isDryRun": False,
            "isSuccess": True,
            "status": "success",
            "views.update.SuccessResponseItems": 1,
        } == event
