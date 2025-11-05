import pytest

from cognite.neat._data_model.deployer._differ_container import ContainerDiffer
from cognite.neat._data_model.deployer._differ_data_model import DataModelDiffer
from cognite.neat._data_model.deployer._differ_view import ViewDiffer
from cognite.neat._data_model.deployer.data_classes import (
    ResourceChange,
    ResourceDeploymentPlan,
    ResourceDeploymentPlanList,
    SeverityType,
)
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


class TestResourceDeploymentPlanList:
    def test_consolidate_resources(self) -> None:
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

        plan = ResourceDeploymentPlanList(
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
                            changes=ViewDiffer().diff(current_view, new_view),
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

        consolidated_plan = plan.consolidate_changes()

        assert len(consolidated_plan) == 3
        resource_plan: ResourceDeploymentPlan
        for resource_plan in consolidated_plan.data:
            # All removed properties, constraints, indexes, and views should lead to unchanged resources
            assert len(resource_plan.unchanged) == 1
            assert len(resource_plan.to_create) == 0
            assert len(resource_plan.to_update) == 0
            assert len(resource_plan.to_delete) == 0
