from cognite.neat._client.api import NeatAPI
from cognite.neat._client.data_classes import StatisticsResponse
from cognite.neat._utils.http_client import ParametersRequest


class StatisticsAPI(NeatAPI):
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
