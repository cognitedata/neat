from collections.abc import Sequence

from cognite.neat._data_model.models.dms import DataModelReference, DataModelResponse
from cognite.neat._utils.http_client import RequestMessage, ParamRequest
from .api import NeatAPI


class DataModelsAPI(NeatAPI):
    def list(
        self, space: str | None = None, all_versions: bool = False, include_global: bool = False, limit: int = 10,
    ) -> list[DataModelResponse]:
        parameters: dict[str, str | int] = {}

        messages = self._http_client.request_with_retries(
            ParamRequest(
                self._config.create_api_url("/models/datamodels"),
                "GET",
                parameters={
                    "space": space,
                    "allVersions": str(all_versions).lower(),
                    "includeGlobal": str(include_global).lower(),
                    "limit": limit,
                }
            )
        )
