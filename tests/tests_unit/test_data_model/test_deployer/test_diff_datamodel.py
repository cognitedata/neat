import pytest

from cognite.neat._data_model.deployer._differ_data_model import DataModelDiffer
from cognite.neat._data_model.deployer.data_classes import (
    PrimitivePropertyChange,
    PropertyChange,
    SeverityType,
)
from cognite.neat._data_model.models.dms import DataModelRequest, ViewReference


class TestDataModelDiffer:
    cdf_datamodel = DataModelRequest(
        space="test_space",
        externalId="test_model",
        version="v1",
        name="My Model",
        description="This is my model",
        views=[
            ViewReference(space="test_space", external_id="view_1", version="v1"),
        ],
    )
    changed_datamodel = DataModelRequest(
        space="test_space",
        externalId="test_model",
        version="v1",
        name="This is updated",
        description="This is an update",
        views=[
            ViewReference(space="test_space", external_id="view_1", version="v1"),
            ViewReference(space="test_space", external_id="view_2", version="v1"),
        ],
    )

    @pytest.mark.parametrize(
        "resource,expected_diff",
        [
            pytest.param(
                cdf_datamodel,
                [],
                id="no changes",
            ),
            pytest.param(
                changed_datamodel,
                [
                    PrimitivePropertyChange(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        old_value="My Model",
                        new_value="This is updated",
                    ),
                    PrimitivePropertyChange(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        old_value="This is my model",
                        new_value="This is an update",
                    ),
                    PrimitivePropertyChange(
                        field_path="views",
                        item_severity=SeverityType.SAFE,
                        old_value=str(cdf_datamodel.views),
                        new_value=str(changed_datamodel.views),
                    ),
                ],
                id="name, description and views changed",
            ),
        ],
    )
    def test_datamodel_diff(self, resource: DataModelRequest, expected_diff: list[PropertyChange]) -> None:
        actual_diffs = DataModelDiffer().diff(self.cdf_datamodel, resource)
        assert expected_diff == actual_diffs
