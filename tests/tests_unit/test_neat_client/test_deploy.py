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
