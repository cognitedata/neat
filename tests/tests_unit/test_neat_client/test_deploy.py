from collections.abc import Callable, Iterable

import pytest
from cognite.client import data_modeling as dm
from cognite.client.data_classes._base import CogniteResourceList
from cognite.client.exceptions import CogniteAPIError

from cognite.neat.core._client.testing import monkeypatch_neat_client
from tests.utils import as_read_containers, as_read_spaces


def deploy_test_cases() -> Iterable:
    yield pytest.param(
        dm.SpaceApplyList(
            [
                dm.SpaceApply("space1", "Description of space 1", "Space 1"),
                dm.SpaceApply("space2", "Description of space 2", "Space 2"),
            ]
        ),
        as_read_spaces,
        "spaces",
        id="Deploy spaces",
    )
    yield pytest.param(
        dm.ContainerApplyList(
            [
                dm.ContainerApply(
                    "my_space",
                    "container1",
                    {
                        "name": dm.ContainerProperty(dm.data_types.Text()),
                        "tags": dm.ContainerProperty(dm.data_types.Text(is_list=True, max_list_size=2000)),
                    },
                    "Description of container 1",
                    "Container 1",
                    used_for="node",
                ),
                dm.ContainerApply(
                    "my_space",
                    "container2",
                    {
                        "source": dm.ContainerProperty(dm.data_types.Text()),
                        "createdDate": dm.ContainerProperty(dm.data_types.Date()),
                    },
                    "Description of container 2",
                    "Container 2",
                    used_for="node",
                ),
            ]
        ),
        as_read_containers,
        "containers",
        id="Deploy containers",
    )


class TestDeployDataModelResources:
    @pytest.mark.parametrize("two_resources, as_read, api_name", list(deploy_test_cases()))
    def test_deploy_existing_skip(self, two_resources: CogniteResourceList, as_read: Callable, api_name: str) -> None:
        with monkeypatch_neat_client() as client:
            api = getattr(client.data_modeling, api_name)
            api.retrieve.return_value = as_read(two_resources[1:])

            result = client.deploy(two_resources, existing="skip")

        assert api.apply.call_count == 1
        assert api.apply.call_args[0][0] == two_resources[:1]
        assert result.status == "success"

    @pytest.mark.parametrize("two_resources, as_read, api_name", list(deploy_test_cases()))
    def test_deploy_existing_fail(self, two_resources: CogniteResourceList, as_read: Callable, api_name: str) -> None:
        with monkeypatch_neat_client() as client:
            api = getattr(client.data_modeling, api_name)
            api.retrieve.return_value = as_read(two_resources[1:])

            result = client.deploy(two_resources, existing="fail")

        assert api.apply.call_count == 0
        assert result.status == "failure"
        assert result.existing == [two_resources[1].as_id()]

    @pytest.mark.parametrize("two_resources, as_read, api_name", list(deploy_test_cases()))
    def test_deploy_existing_update(self, two_resources: CogniteResourceList, as_read: Callable, api_name: str) -> None:
        with monkeypatch_neat_client() as client:
            api = getattr(client.data_modeling, api_name)
            cdf_resource = as_read(two_resources[:1])
            # Note all data modeling resources have name and description properties
            cdf_resource[0].name = "Last name"
            cdf_resource[0].description = "Last description"
            api.retrieve.return_value = cdf_resource

            result = client.deploy(two_resources, existing="update")

        # The first space is created, the second is updated
        assert api.apply.call_count == 2
        # Create call
        assert api.apply.call_args_list[0][0] == (two_resources[1:],)
        # Update call
        assert api.apply.call_args_list[1][0] == (two_resources[:1],)
        assert result.status == "success"
        assert result.to_create == [two_resources[1].as_id()]
        assert len(result.diffs) == 1
        difference = result.diffs[0]
        assert {prop.location for prop in difference.changed} == {"name", "description"}

    @pytest.mark.parametrize("two_resources, as_read, api_name", list(deploy_test_cases()))
    def test_deploy_existing_force(self, two_resources: CogniteResourceList, as_read: Callable, api_name: str) -> None:
        # Note in reality, spaces will not fail to update, but this tests the logic of the deploy function
        with monkeypatch_neat_client() as client:
            api = getattr(client.data_modeling, api_name)
            cdf_resources = as_read(two_resources[:1])
            cdf_resources[0].name = "Last name"
            cdf_resources[0].description = "Last description"
            api.retrieve.return_value = cdf_resources
            api.apply.side_effect = [
                as_read(two_resources[1:]),
                CogniteAPIError("Update failed", code=400),
                as_read(two_resources[:1]),  # Recreate the first resource
            ]

            result = client.deploy(two_resources, existing="force")

        # The first space is created, update fails, then the second space is updated
        assert api.apply.call_count == 3
        # Create call
        assert api.apply.call_args_list[0][0] == (two_resources[1:],)
        # Failed call
        assert api.apply.call_args_list[1][0] == (two_resources[:1],)
        # Recreate call
        assert api.apply.call_args_list[2][0] == (two_resources[:1],)
        # Delete call
        assert api.delete.call_count == 1

        assert result.status == "success"
        assert len(result.forced) == 1
        forced = result.forced[0]
        assert forced.resource_id == two_resources[0].as_id()
        assert forced.reason == "Update failed | code: 400 | X-Request-ID: None"

    @pytest.mark.parametrize("two_resources, as_read, api_name", list(deploy_test_cases()))
    def test_deploy_space_existing_recreate(
        self, two_resources: CogniteResourceList, as_read: Callable, api_name: str
    ) -> None:
        with monkeypatch_neat_client() as client:
            api = getattr(client.data_modeling, api_name)
            api.retrieve.return_value = as_read(two_resources[1:])

            result = client.deploy(two_resources, existing="recreate")

        assert api.delete.call_count == 1
        assert api.delete.call_args[0][0] == [two_resources[1].as_id()]
        assert api.apply.call_count == 1
        assert api.apply.call_args[0][0] == two_resources

        assert result.status == "success"
