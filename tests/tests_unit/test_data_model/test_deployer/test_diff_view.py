import pytest

from cognite.neat._data_model.deployer._differ_view import (
    ViewDiffer,
    ViewPropertyDiffer,
)
from cognite.neat._data_model.deployer.data_classes import PropertyChange
from cognite.neat._data_model.models.dms import ViewRequest


class TestViewDiffer:
    cdf_view = ViewRequest(

    )
    def test_container_diff(self, resource: ViewRequest, expected_diff: list[PropertyChange]) -> None:
        actual_diffs = ViewPropertyDiffer().diff(self.cdf_view, resource)
        assert expected_diff == actual_diffs