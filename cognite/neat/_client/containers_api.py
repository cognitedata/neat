from __future__ import annotations

from collections.abc import Sequence

from cognite.neat._data_model.models.dms import ContainerReference, ContainerRequest, ContainerResponse, DataModelBody
from cognite.neat._utils.http_client import ItemIDBody, ItemsRequest, ParametersRequest
from cognite.neat._utils.useful_types import PrimitiveType

from .api import NeatAPI
from .data_classes import PagedResponse


class ContainersAPI(NeatAPI):
    ENDPOINT = "/models/containers"
    LIST_REQUEST_LIMIT = 1000

    def apply(self, items: Sequence[ContainerRequest]) -> list[ContainerResponse]:
        """Apply (create or update) containers in CDF.

        Args:
            items: List of ContainerRequest objects to apply.
        Returns:
            List of ContainerResponse objects.
        """
        if not items:
            return []
        if len(items) > 100:
            raise ValueError("Cannot apply more than 100 containers at once.")
        result = self._http_client.request_with_retries(
            ItemsRequest(
                endpoint_url=self._config.create_api_url(self.ENDPOINT),
                method="POST",
                body=DataModelBody(items=items),
            )
        )
        result.raise_for_status()
        result = PagedResponse[ContainerResponse].model_validate_json(result.success_response.body)
        return result.items

    def retrieve(
        self,
        items: list[ContainerReference],
    ) -> list[ContainerResponse]:
        """Retrieve containers by their identifiers.

        Args:
            items: List of (space, external_id) tuples identifying the containers to retrieve.

        Returns:
            List of ContainerResponse objects.
        """
        if not items:
            return []
        if len(items) > 1000:
            raise ValueError("Cannot retrieve more than 1000 containers at once.")

        result = self._http_client.request_with_retries(
            ItemsRequest(
                endpoint_url=self._config.create_api_url(f"{self.ENDPOINT}/byids"),
                method="POST",
                body=ItemIDBody(items=items),
            )
        )
        result.raise_for_status()
        result = PagedResponse[ContainerResponse].model_validate_json(result.success_response.body)
        return result.items

    def delete(self, items: list[ContainerReference]) -> list[ContainerReference]:
        """Delete containers by their identifiers.

        Args:
            items: List of ContainerReference objects identifying the containers to delete.

        Returns:
            List of ContainerReference objects representing the deleted containers.
        """
        if not items:
            return []
        if len(items) > 100:
            raise ValueError("Cannot delete more than 100 containers at once.")

        result = self._http_client.request_with_retries(
            ItemsRequest(
                endpoint_url=self._config.create_api_url(f"{self.ENDPOINT}/delete"),
                method="POST",
                body=ItemIDBody(items=items),
            )
        )
        result.raise_for_status()
        result = PagedResponse[ContainerReference].model_validate_json(result.success_response.body)
        return result.items

    def list(
        self,
        space: str | None = None,
        include_global: bool = False,
        limit: int | None = 10,
    ) -> list[ContainerResponse]:
        """List containers in CDF Project.

        Args:
            space: If specified, only containers in this space are returned.
            include_global: If True, include global containers.
            limit: Maximum number of containers to return. If None, return all containers.

        Returns:
            List of ContainerResponse objects.
        """
        if limit is not None and limit < 0:
            raise ValueError("Limit must be non-negative.")
        elif limit is not None and limit == 0:
            return []
        parameters: dict[str, PrimitiveType] = {"includeGlobal": include_global}
        if space is not None:
            parameters["space"] = space
        cursor: str | None = None
        container_responses: list[ContainerResponse] = []
        while True:
            if cursor is not None:
                parameters["cursor"] = cursor
            if limit is None:
                parameters["limit"] = self.LIST_REQUEST_LIMIT
            else:
                parameters["limit"] = min(self.LIST_REQUEST_LIMIT, limit - len(container_responses))
            result = self._http_client.request_with_retries(
                ParametersRequest(
                    endpoint_url=self._config.create_api_url(self.ENDPOINT),
                    method="GET",
                    parameters=parameters,
                )
            )
            result.raise_for_status()
            result = PagedResponse[ContainerResponse].model_validate_json(result.success_response.body)
            container_responses.extend(result.items)
            cursor = result.next_cursor
            if cursor is None or (limit is not None and len(container_responses) >= limit):
                break
        return container_responses
