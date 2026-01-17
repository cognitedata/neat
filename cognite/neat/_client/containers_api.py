from collections.abc import Sequence

from cognite.neat._data_model.models.dms import ContainerReference, ContainerRequest, ContainerResponse
from cognite.neat._utils.http_client import HTTPClient, SuccessResponse

from .api import Endpoint, NeatAPI
from .config import NeatClientConfig
from .data_classes import PagedResponse
from .filters import ContainerFilter


class ContainersAPI(NeatAPI):
    def __init__(self, neat_config: NeatClientConfig, http_client: HTTPClient) -> None:
        super().__init__(
            neat_config,
            http_client,
            endpoint_map={
                "apply": Endpoint("POST", "models/containers", item_limit=100),
                "retrieve": Endpoint("POST", "models/containers/byids", item_limit=100),
                "delete": Endpoint("POST", "models/containers/delete", item_limit=100),
                "list": Endpoint("GET", "models/containers", item_limit=1000),
            },
        )

    def _validate_page_response(self, response: SuccessResponse) -> PagedResponse[ContainerResponse]:
        return PagedResponse[ContainerResponse].model_validate_json(response.body)

    def _validate_id_response(self, response: SuccessResponse) -> list[ContainerReference]:
        return PagedResponse[ContainerReference].model_validate_json(response.body).items

    def apply(self, items: Sequence[ContainerRequest]) -> list[ContainerResponse]:
        """Apply (create or update) containers in CDF.

        Args:
            items: List of ContainerRequest objects to apply.
        Returns:
            List of ContainerResponse objects.
        """
        return self._request_item_response(items, "apply")

    def retrieve(self, items: list[ContainerReference]) -> list[ContainerResponse]:
        """Retrieve containers by their identifiers.

        Args:
            items: List of (space, external_id) tuples identifying the containers to retrieve.

        Returns:
            List of ContainerResponse objects.
        """
        return self._request_item_response(items, "retrieve")

    def delete(self, items: list[ContainerReference]) -> list[ContainerReference]:
        """Delete containers by their identifiers.

        Args:
            items: List of ContainerReference objects identifying the containers to delete.

        Returns:
            List of ContainerReference objects representing the deleted containers.
        """
        return self._request_id_response(items, "delete")

    def list(
        self, space: str | None = None, include_global: bool = False, limit: int | None = 10
    ) -> list[ContainerResponse]:
        """List containers in CDF Project.

        Args:
            space: If specified, only containers in this space are returned.
            include_global: If True, include global containers.
            limit: Maximum number of containers to return. If None, return all containers.

        Returns:
            List of ContainerResponse objects.
        """
        filter = ContainerFilter(space=space, include_global=include_global)
        return self._list(limit=limit, params=filter.dump())
