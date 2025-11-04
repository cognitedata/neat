import pytest

from cognite.neat._data_model.deployer._differ_data_model import DataModelDiffer
from cognite.neat._data_model.deployer.data_classes import (
    AddedField,
    ChangedField,
    FieldChange,
    RemovedField,
    SeverityType,
)
from cognite.neat._data_model.models.dms import DataModelRequest, ViewReference


class TestDataModelDiffer:
    current_datamodel = DataModelRequest(
        space="test_space",
        externalId="test_model",
        version="v1",
        name="My Model",
        description="This is my model",
        views=[
            ViewReference(space="test_space", external_id="UnchangedView", version="v1"),
            ViewReference(space="test_space", external_id="ViewToRemove", version="v1"),
        ],
    )
    new_datamodel = DataModelRequest(
        space="test_space",
        externalId="test_model",
        version="v1",
        name="This is updated",
        description="This is an update",
        views=[
            ViewReference(space="test_space", external_id="UnchangedView", version="v1"),
            ViewReference(space="test_space", external_id="ViewToAdd", version="v1"),
        ],
    )
    new_datamodel_reorder = DataModelRequest(
        space="test_space",
        externalId="test_model",
        version="v1",
        name="My Model",
        description="This is my model",
        views=[
            ViewReference(space="test_space", external_id="ViewToRemove", version="v1"),
            ViewReference(space="test_space", external_id="UnchangedView", version="v1"),
        ],
    )

    @pytest.mark.parametrize(
        "resource,expected_diff",
        [
            pytest.param(
                current_datamodel,
                [],
                id="no changes",
            ),
            pytest.param(
                new_datamodel,
                [
                    ChangedField(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        current_value="My Model",
                        new_value="This is updated",
                    ),
                    ChangedField(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        current_value="This is my model",
                        new_value="This is an update",
                    ),
                    AddedField(
                        field_path="views",
                        item_severity=SeverityType.SAFE,
                        new_value=new_datamodel.views[1],  # type: ignore[index]
                    ),
                    RemovedField(
                        field_path="views",
                        item_severity=SeverityType.BREAKING,
                        current_value=current_datamodel.views[1],  # type: ignore[index]
                    ),
                ],
                id="name, description and views changed",
            ),
            pytest.param(
                new_datamodel_reorder,
                [
                    ChangedField(
                        field_path="views",
                        item_severity=SeverityType.SAFE,
                        current_value=str(current_datamodel.views),
                        new_value=str(new_datamodel_reorder.views),
                    )
                ],
                id="views reordered",
            ),
        ],
    )
    def test_datamodel_diff(self, resource: DataModelRequest, expected_diff: list[FieldChange]) -> None:
        actual_diffs = DataModelDiffer().diff(self.current_datamodel, resource)
        assert expected_diff == actual_diffs
