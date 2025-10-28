import pytest

from cognite.neat._data_model.deployer._differ_container import ContainerDiffer
from cognite.neat._data_model.deployer.data_classes import PrimitivePropertyChange, PropertyChange, SeverityType
from cognite.neat._data_model.models.dms import ContainerRequest


class TestContainerDiffer:
    cdf_container =

    @pytest.mark.parametrize(
        "resource,expected_diff",
        [
            pytest.param(
                cdf_container,
                [],
                id="no changes",
            ),
        ],
    )
    def test_diff(self, resource: ContainerRequest, expected_diff: list[PropertyChange]) -> None:
        actual_diffs = ContainerDiffer().diff(
            self.cdf_container,
            resource,
        )
        assert actual_diffs == expected_diff
