import pytest
from cognite.client import data_modeling as dm

from cognite.neat.core._client.testing import monkeypatch_neat_client
from tests.utils import as_read_space


@pytest.fixture()
def two_spaces() -> dm.SpaceApplyList:
    return dm.SpaceApplyList(
        [
            dm.SpaceApply("space1", "Description of space 1", "Space 1"),
            dm.SpaceApply("space2", "Description of space 2", "Space 2"),
        ]
    )


class TestDeploySpace:
    def test_deploy_space_existing_skip(self, two_spaces: dm.SpaceApplyList) -> None:
        with monkeypatch_neat_client() as client:
            client.data_modeling.spaces.retrieve.return_value = dm.SpaceList([as_read_space(two_spaces[1])])
            result = client.deploy(two_spaces, existing="skip")

        assert client.data_modeling.spaces.apply.call_count == 1
        assert client.data_modeling.spaces.apply.call_args[0][0] == dm.SpaceApplyList([two_spaces[0]])
        assert result.status == "success"

    def test_deploy_space_existing_fail(self, two_spaces: dm.SpaceApplyList) -> None:
        with monkeypatch_neat_client() as client:
            client.data_modeling.spaces.retrieve.return_value = dm.SpaceList([as_read_space(two_spaces[1])])
            result = client.deploy(two_spaces, existing="fail")

        assert client.data_modeling.spaces.apply.call_count == 0
        assert result.status == "failure"
        assert result.existing == [two_spaces[1].space]

    def test_deploy_space_existing_update(self, two_spaces: dm.SpaceApplyList) -> None:
        with monkeypatch_neat_client() as client:
            cdf_space = as_read_space(two_spaces[0])
            cdf_space.name = "Last name"
            cdf_space.description = "Last description"
            client.data_modeling.spaces.retrieve.return_value = dm.SpaceList([cdf_space])
            result = client.deploy(two_spaces, existing="update")

        # The first space is created, the second is updated
        assert client.data_modeling.spaces.apply.call_count == 2
        # Create call
        assert client.data_modeling.spaces.apply.call_args_list[0][0] == (dm.SpaceApplyList([two_spaces[1]]),)
        # Update call
        assert client.data_modeling.spaces.apply.call_args_list[1][0] == (dm.SpaceApplyList([two_spaces[0]]),)
        assert result.status == "success"
        assert result.to_create == [two_spaces[1].space]
        assert len(result.diffs) == 1
        difference = result.diffs[0]
        assert {prop.location for prop in difference.changed} == {"name", "description"}

    def test_deploy_space_existing_recreate(self, two_spaces: dm.SpaceApplyList) -> None:
        with monkeypatch_neat_client() as client:
            client.data_modeling.spaces.retrieve.return_value = dm.SpaceList([as_read_space(two_spaces[1])])
            result = client.deploy(two_spaces, existing="recreate")

        assert client.data_modeling.spaces.delete.call_count == 1
        assert client.data_modeling.spaces.delete.call_args[0][0] == [two_spaces[1].space]
        assert client.data_modeling.spaces.apply.call_count == 1
        assert client.data_modeling.spaces.apply.call_args[0][0] == two_spaces

        assert result.status == "success"
