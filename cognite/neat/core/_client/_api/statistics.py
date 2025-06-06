import itertools
from typing import overload

from cognite.client._api_client import APIClient
from cognite.client._cognite_client import CogniteClient
from cognite.client.config import ClientConfig
from cognite.client.data_classes.data_modeling.ids import _load_space_identifier
from cognite.client.exceptions import CogniteAPIError
from cognite.client.utils.useful_types import SequenceNotStr

from cognite.neat.core._client.data_classes.statistics import (
    ProjectStatsAndLimits,
    SpaceInstanceCounts,
    SpaceInstanceCountsList,
)
from cognite.neat.core._constants import DMS_INSTANCE_LIMIT_MARGIN
from cognite.neat.core._issues import NeatIssue
from cognite.neat.core._issues.errors import WillExceedInstanceLimitError
from cognite.neat.core._issues.warnings import NeatValueWarning


class StatisticsAPI(APIClient):
    _RESOURCE_PATH = "/models/statistics"

    def __init__(self, config: ClientConfig, api_version: str | None, cognite_client: CogniteClient) -> None:
        # This is an alpha API, which requires a specific version.
        super().__init__(config, "v1", cognite_client)
        self._RETRIEVE_LIMIT = 100

    def project(self) -> ProjectStatsAndLimits:
        """`Retrieve project-wide usage data and limits

        Returns the usage data and limits for a project's data modelling usage, including data model schemas
        and graph instances

        Returns:
            ProjectStatsAndLimits: The requested statistics and limits

        Examples:
            Fetch project statistics (and limits) and check the current number of data models vs.
            and how many more can be created:
                >>> from cognite.neat.core._client import NeatClient
                >>> client = NeatClient()
                >>> stats = client.instance_statistics.project()
                >>> num_dm = stats.data_models.current
                >>> num_dm_left = stats.data_models.limit - num_dm
        """
        response_data = self._get(self._RESOURCE_PATH).json()
        if "project" not in response_data:
            response_data["project"] = self._cognite_client._config.project
        return ProjectStatsAndLimits._load(response_data)

    @overload
    def list(self, space: str) -> SpaceInstanceCounts: ...

    @overload
    def list(self, space: SequenceNotStr[str] | None = None) -> SpaceInstanceCountsList: ...

    def list(self, space: str | SequenceNotStr[str] | None = None) -> SpaceInstanceCounts | SpaceInstanceCountsList:
        """`Retrieve usage data and limits per space

        Args:
            space (str | SequenceNotStr[str] | None): The space or spaces to retrieve statistics for.
                If None, all spaces will be retrieved.

        Returns:
            SpaceInstanceCounts | SpaceInstanceCountsList: InstanceStatsPerSpace if a single space is given, else
                InstanceStatsList (which is a list of InstanceStatsPerSpace)

        Examples:
            Fetch statistics for a single space:
                >>> from cognite.neat.core._client import NeatClient
                >>> client = NeatClient()
                >>> res = client.instance_statistics.list("my-space")
            Fetch statistics for multiple spaces:
                >>> res = client.instance_statistics.list(
                ...     ["my-space1", "my-space2"]
                ... )
            Fetch statistics for all spaces (ignores the 'space' argument):
                >>> res = client.instance_statistics.list(return_all=True)
        """
        if space is None:
            return SpaceInstanceCountsList._load(self._get(self._RESOURCE_PATH + "/spaces").json()["items"])

        is_single = isinstance(space, str)

        ids = _load_space_identifier(space)
        result = SpaceInstanceCountsList._load(
            itertools.chain.from_iterable(
                self._post(self._RESOURCE_PATH + "/spaces/byids", json={"items": chunk.as_dicts()}).json()["items"]
                for chunk in ids.chunked(self._RETRIEVE_LIMIT)
            )
        )
        if is_single:
            return result[0]
        return result

    def validate_cdf_project_instance_capacity(self, total_instances: int) -> NeatIssue | None:
        """Validates if the current project instance capacity can accommodate the given number of instances.

        Args:
            total_instances (int): The total number of instances to check against the project's capacity.

        Returns:
            NeatIssue | None: Returns a warning if the capacity is exceeded, otherwise None.

        """
        try:
            stats = self.project()
        except CogniteAPIError as e:
            # This endpoint is not yet in alpha, it may change or not be available.
            return NeatValueWarning(f"Cannot check project instance capacity. Endpoint not available: {e}")
        instance_capacity = stats.instances.instances_limit - stats.instances.instances
        if total_instances + DMS_INSTANCE_LIMIT_MARGIN > instance_capacity:
            # This breaks the general contract of loaders, which is to not raise exceptions unless
            # stop_on_exception is True.
            # However, this is a special case where we do not want to proceed no matter what.
            raise WillExceedInstanceLimitError(total_instances, stats.project, instance_capacity)
        return None
