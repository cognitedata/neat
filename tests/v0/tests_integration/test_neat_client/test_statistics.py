import pytest

from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._client.data_classes.statistics import ProjectStatsAndLimits


@pytest.fixture(scope="session")
def project_usage(neat_client: NeatClient) -> ProjectStatsAndLimits:
    """Fixture to retrieve project usage statistics."""
    return neat_client.instance_statistics.project()


class TestStatisticsAPI:
    def test_list_project_instance_usage(self, project_usage: ProjectStatsAndLimits) -> None:
        assert project_usage.instances.instances < project_usage.instances.instances_limit

    def test_list_space_instance_usage(self, neat_client: NeatClient) -> None:
        spaces = neat_client.data_modeling.spaces.list(limit=1)
        assert len(spaces) > 0
        selected_space = spaces[0].space

        space_usage = neat_client.instance_statistics.list(space=selected_space)

        assert space_usage.space == selected_space

    def test_list_all_spaces(self, neat_client: NeatClient, project_usage: ProjectStatsAndLimits) -> None:
        space_usages = neat_client.instance_statistics.list()

        assert len(space_usages) > 0
        total = sum(space_usage.nodes + space_usage.edges for space_usage in space_usages)

        assert total == project_usage.instances.instances
