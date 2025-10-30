import pytest

from cognite.neat._data_model.deployer._differ_space import SpaceDiffer
from cognite.neat._data_model.deployer.data_classes import ChangedField, FieldChange, SeverityType
from cognite.neat._data_model.models.dms import SpaceRequest


class TestSpaceDiffer:
    cdf_space = SpaceRequest(
        space="name1",
        name="Space One",
        description="This is space one.",
    )

    @pytest.mark.parametrize(
        "resource,expected_diff",
        [
            pytest.param(
                cdf_space,
                [],
                id="no changes",
            ),
            pytest.param(
                SpaceRequest(
                    space="name1",
                    name="Space 1",
                    description="This is space 1.",
                ),
                [
                    ChangedField(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        current_value="Space One",
                        new_value="Space 1",
                    ),
                    ChangedField(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        current_value="This is space one.",
                        new_value="This is space 1.",
                    ),
                ],
                id="Name and description changed",
            ),
        ],
    )
    def test_diff(self, resource: SpaceRequest, expected_diff: list[FieldChange]) -> None:
        actual_diffs = SpaceDiffer().diff(
            self.cdf_space,
            resource,
        )
        assert actual_diffs == expected_diff
