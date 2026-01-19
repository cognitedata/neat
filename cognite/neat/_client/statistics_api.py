from cognite.neat._utils.http_client import HTTPClient, ParametersRequest

from .config import NeatClientConfig
from .data_classes import StatisticsResponse


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
