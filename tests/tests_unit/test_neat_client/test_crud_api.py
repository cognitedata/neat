from collections.abc import Iterable

import pytest
from cognite.client.data_classes.data_modeling import ContainerApply

from cognite.neat.core._client._api.crud import ContainerCrudAPI
from cognite.neat.core._client.data_classes.deploy_result import ResourceDifference


def container_difference_test_cases() -> Iterable: ...


def container_merge_test_cases() -> Iterable: ...


class TestContainerCrudAPI:
    @pytest.mark.parametrize("new, previous, expected", list(container_difference_test_cases()))
    def test_difference(self, new: ContainerApply, previous: ContainerApply, expected: ResourceDifference) -> None:
        assert ContainerCrudAPI.difference(new, previous) == expected

    @pytest.mark.parametrize("new, previous, expected", list(container_merge_test_cases()))
    def test_merge(self, new: ContainerApply, previous: ContainerApply, expected: ContainerApply) -> None:
        assert ContainerCrudAPI.merge(new, previous) == expected
