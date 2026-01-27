import json

from cognite.neat._utils.http_client import HTTPClient, ParametersRequest
from cognite.neat._utils.http_client._data_classes import SimpleBodyRequest

from .config import NeatClientConfig
from .data_classes import SpaceStatisticsResponse, StatisticsResponse


class StatisticsAPI:
    def __init__(self, neat_config: NeatClientConfig, http_client: HTTPClient) -> None:
        self._config = neat_config
        self._http_client = http_client

    def project(self) -> StatisticsResponse:
        """Retrieve project-wide usage data and limits.

        Returns:
            StatisticsResponse object.
        """

        result = self._http_client.request_with_retries(
            ParametersRequest(
                endpoint_url=self._config.create_api_url("/models/statistics"),
                method="GET",
                parameters=None,
            )
        )

        result.raise_for_status()
        result = StatisticsResponse.model_validate_json(result.success_response.body)
        return result

    def space_statistics(self, spaces: list[str]) -> SpaceStatisticsResponse:
        """Retrieve space-wise usage data and limits.

        Args:
            spaces: List of space identifiers to retrieve statistics for.

        Returns:
            SpaceStatisticsResponse object.
        """

        body = {"items": [{"space": space} for space in spaces]}

        result = self._http_client.request_with_retries(
            SimpleBodyRequest(
                endpoint_url=self._config.create_api_url("/models/statistics/spaces/byids"),
                method="POST",
                body=json.dumps(body),
            )
        )

        result.raise_for_status()
        result = SpaceStatisticsResponse.model_validate_json(result.success_response.body)
        return result
