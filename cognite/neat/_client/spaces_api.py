from __future__ import annotations

from cognite.neat._data_model.models.dms import DataModelBody, SpaceRequest, SpaceResponse
from cognite.neat._data_model.models.dms._references import SpaceReference
from cognite.neat._utils.http_client import ItemIDBody, ItemsRequest, ParametersRequest
from cognite.neat._utils.useful_types import PrimitiveType

from .api import NeatAPI
from .data_classes import PagedResponse


class SpacesAPI(NeatAPI):
    ENDPOINT = "/models/spaces"

    def apply(self, spaces: list[SpaceRequest]) -> list[SpaceResponse]:
        """Apply (create or update) spaces in CDF.

        Args:
            spaces: List of SpaceRequest objects to apply.
        Returns:
            List of SpaceResponse objects.
        """
        if not spaces:
            return []
        if len(spaces) > 100:
            raise ValueError("Cannot apply more than 100 spaces at once.")
        result = self._http_client.request_with_retries(
            ItemsRequest(
                endpoint_url=self._config.create_api_url(self.ENDPOINT),
                method="POST",
                body=DataModelBody(items=spaces),
            )
        )
        result.raise_for_status()
        result = PagedResponse[SpaceResponse].model_validate_json(result.success_response.body)
        return result.items

    def retrieve(self, spaces: list[SpaceReference]) -> list[SpaceResponse]:
        """Retrieve spaces by their identifiers.

        Args:
            spaces: List of space identifiers to retrieve.

        Returns:
            List of SpaceResponse objects.
        """
        if not spaces:
            return []
        if len(spaces) > 1000:
            raise ValueError("Cannot retrieve more than 1000 spaces at once.")

        result = self._http_client.request_with_retries(
            ItemsRequest(
                endpoint_url=self._config.create_api_url(f"{self.ENDPOINT}/byids"),
                method="POST",
                body=ItemIDBody(items=spaces),
            )
        )
        result.raise_for_status()
        result = PagedResponse[SpaceResponse].model_validate_json(result.success_response.body)
        return result.items

    def delete(self, spaces: list[SpaceReference]) -> list[SpaceReference]:
        """Delete spaces by their identifiers.

        Args:
            spaces: List of space identifiers to delete.
        Returns:
            List of SpaceReference objects representing the deleted spaces.
        """
        if not spaces:
            return []
        if len(spaces) > 100:
            raise ValueError("Cannot delete more than 100 spaces at once.")
        result = self._http_client.request_with_retries(
            ItemsRequest(
                endpoint_url=self._config.create_api_url(f"{self.ENDPOINT}/delete"),
                method="POST",
                body=ItemIDBody(items=spaces),
            )
        )
        result.raise_for_status()
        result = PagedResponse[SpaceReference].model_validate_json(result.success_response.body)
        return result.items

    def list(
        self,
        include_global: bool = False,
        limit: int = 10,
    ) -> list[SpaceResponse]:
        """List spaces in CDF Project.

        Args:
            include_global: If True, include global spaces.
            limit: Maximum number of spaces to return. Max is 1000.

        Returns:
            List of SpaceResponse objects.
        """
        if limit > 1000:
            raise ValueError("Pagination is not (yet) supported for listing spaces. The maximum limit is 1000.")
        parameters: dict[str, PrimitiveType] = {
            "includeGlobal": include_global,
            "limit": limit,
        }
        result = self._http_client.request_with_retries(
            ParametersRequest(
                endpoint_url=self._config.create_api_url(self.ENDPOINT),
                method="GET",
                parameters=parameters,
            )
        )
        result.raise_for_status()
        result = PagedResponse[SpaceResponse].model_validate_json(result.success_response.body)
        return result.items
