from cognite.neat._data_model.models.dms import DataModelReference, DataModelResponse
from cognite.neat._utils.http_client import ItemIDBody, ItemsRequest, ParametersRequest
from cognite.neat._utils.useful_types import PrimitiveType

from .api import NeatAPI
from .data_classes import PagedResponse


class DataModelsAPI(NeatAPI):
    def retrieve(
        self,
        items: list[DataModelReference],
    ) -> list[DataModelResponse]:
        """Retrieve data models by their identifiers.

        Args:
            items: List of data models references identifying the data models to retrieve.
        Returns:
            List of DataModelResponse objects.
        """
        if not items:
            return []
        if len(items) > 1000:
            raise ValueError("Cannot retrieve more than 1000 containers at once.")

        result = self._http_client.request_with_retries(
            ItemsRequest(
                endpoint_url=self._config.create_api_url("/models/datamodels/byids"),
                method="POST",
                body=ItemIDBody(items=items),
            )
        )
        result.raise_for_status()
        result = PagedResponse[DataModelResponse].model_validate_json(result.success_response.data)
        return result.items

    def list(
        self,
        space: str | None = None,
        all_versions: bool = False,
        include_global: bool = False,
        limit: int = 10,
    ) -> list[DataModelResponse]:
        """List data models in CDF Project."""
        if limit > 1000:
            raise ValueError("Pagination is not (yet) supported for listing data models. The maximum limit is 1000.")
        parameters: dict[str, PrimitiveType] = {
            "allVersions": all_versions,
            "includeGlobal": include_global,
            "limit": limit,
        }
        if space is not None:
            parameters["space"] = space
        result = self._http_client.request_with_retries(
            ParametersRequest(
                endpoint_url=self._config.create_api_url("/models/datamodels"),
                method="GET",
                parameters=parameters,
            )
        )
        result.raise_for_status()
        result = PagedResponse[DataModelResponse].model_validate_json(result.success_response.data)
        return result.items
