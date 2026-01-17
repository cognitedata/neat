from collections.abc import Sequence

from cognite.neat._data_model.models.dms import DataModelReference, DataModelRequest, DataModelResponse
from cognite.neat._utils.http_client import HTTPClient, SuccessResponse

from .api import Endpoint, NeatAPI
from .config import NeatClientConfig
from .data_classes import PagedResponse
from .filters import DataModelFilter


class DataModelsAPI(NeatAPI):
    def __init__(self, neat_config: NeatClientConfig, http_client: HTTPClient) -> None:
        super().__init__(
            neat_config,
            http_client,
            endpoint_map={
                "apply": Endpoint("POST", "/models/datamodels", item_limit=100),
                "retrieve": Endpoint("POST", "/models/datamodels/byids", item_limit=100),
                "delete": Endpoint("POST", "/models/datamodels/delete", item_limit=100),
                "list": Endpoint("GET", "/models/datamodels", item_limit=1000),
            },
        )

    def _validate_page_response(self, response: SuccessResponse) -> PagedResponse[DataModelResponse]:
        return PagedResponse[DataModelResponse].model_validate_json(response.body)

    def _validate_id_response(self, response: SuccessResponse) -> list[DataModelReference]:
        return PagedResponse[DataModelReference].model_validate_json(response.body).items

    def apply(self, data_models: Sequence[DataModelRequest]) -> list[DataModelResponse]:
        """Apply (create or update) data models in CDF.

        Args:
            data_models: List of DataModelRequest objects to apply.
        Returns:
            List of DataModelResponse objects.
        """
        return self._request_item_response(data_models, "apply")

    def retrieve(self, items: list[DataModelReference]) -> list[DataModelResponse]:
        """Retrieve data models by their identifiers.

        Args:
            items: List of data models references identifying the data models to retrieve.
        Returns:
            List of DataModelResponse objects.
        """
        return self._request_item_response(items, "retrieve")

    def delete(self, items: list[DataModelReference]) -> list[DataModelReference]:
        """Delete data models by their identifiers.

        Args:
            items: List of data model references identifying the data models to delete.
        Returns:
            List of DataModelReference objects representing the deleted data models.
        """
        return self._request_id_response(items, "delete")

    def list(
        self,
        space: str | None = None,
        all_versions: bool = False,
        inline_views: bool = False,
        include_global: bool = False,
        limit: int | None = 10,
    ) -> list[DataModelResponse]:
        """List data models in CDF Project.

        Args:
            space: If specified, only data models in this space are returned.
            all_versions: If True, return all versions. If False, only return the latest version.
            inline_views: If True, include views inline in the response.
            include_global: If True, include global data models.
            limit: Maximum number of data models to return. If None, return all data models.

        Returns:
            List of DataModelResponse objects.
        """
        filter = DataModelFilter(
            space=space,
            all_versions=all_versions,
            inline_views=inline_views,
            include_global=include_global,
        )
        return self._list(limit=limit, params=filter.dump())
