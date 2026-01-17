from __future__ import annotations

from collections.abc import Sequence

from cognite.neat._data_model.models.dms import SpaceRequest, SpaceResponse
from cognite.neat._data_model.models.dms._references import SpaceReference
from cognite.neat._utils.http_client import HTTPClient, SuccessResponse

from .api import Endpoint, NeatAPI
from .config import NeatClientConfig
from .data_classes import PagedResponse
from .filters import DataModelingFilter


class SpacesAPI(NeatAPI):
    def __init__(self, neat_config: NeatClientConfig, http_client: HTTPClient) -> None:
        super().__init__(
            neat_config,
            http_client,
            endpoint_map={
                "apply": Endpoint("POST", "/models/spaces", item_limit=100),
                "retrieve": Endpoint("POST", "/models/spaces/byids", item_limit=1000),
                "delete": Endpoint("POST", "/models/spaces/delete", item_limit=100),
                "list": Endpoint("GET", "/models/spaces", item_limit=1000),
            },
        )

    def _validate_page_response(self, response: SuccessResponse) -> PagedResponse[SpaceResponse]:
        return PagedResponse[SpaceResponse].model_validate_json(response.body)

    def _validate_id_response(self, response: SuccessResponse) -> list[SpaceReference]:
        return PagedResponse[SpaceReference].model_validate_json(response.body).items

    def apply(self, spaces: Sequence[SpaceRequest]) -> list[SpaceResponse]:
        """Apply (create or update) spaces in CDF.

        Args:
            spaces: List of SpaceRequest objects to apply.
        Returns:
            List of SpaceResponse objects.
        """
        return self._request_item_response(spaces, "apply")

    def retrieve(self, spaces: list[SpaceReference]) -> list[SpaceResponse]:
        """Retrieve spaces by their identifiers.

        Args:
            spaces: List of space identifiers to retrieve.

        Returns:
            List of SpaceResponse objects.
        """
        return self._request_item_response(spaces, "retrieve")

    def delete(self, spaces: list[SpaceReference]) -> list[SpaceReference]:
        """Delete spaces by their identifiers.

        Args:
            spaces: List of space identifiers to delete.
        Returns:
            List of SpaceReference objects representing the deleted spaces.
        """
        return self._request_id_response(spaces, "delete")

    def list(
        self,
        include_global: bool = False,
        limit: int | None = 10,
    ) -> list[SpaceResponse]:
        """List spaces in CDF Project.

        Args:
            include_global: If True, include global spaces.
            limit: Maximum number of spaces to return. If None, return all spaces.

        Returns:
            List of SpaceResponse objects.
        """
        filter = DataModelingFilter(include_global=include_global)
        return self._list(limit=limit, params=filter.dump())
