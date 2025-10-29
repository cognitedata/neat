from __future__ import annotations

from cognite.neat._data_model.models.dms import SpaceResponse
from cognite.neat._data_model.models.dms._references import SpaceReference
from cognite.neat._utils.http_client import ItemIDBody, ItemsRequest, ParametersRequest
from cognite.neat._utils.useful_types import PrimitiveType

from .api import NeatAPI
from .data_classes import PagedResponse


class SpacesAPI(NeatAPI):
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
                endpoint_url=self._config.create_api_url("/models/spaces/byids"),
                method="POST",
                body=ItemIDBody(items=spaces),
            )
        )
        result.raise_for_status()
        result = PagedResponse[SpaceResponse].model_validate_json(result.success_response.body)
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
                endpoint_url=self._config.create_api_url("/models/spaces"),
                method="GET",
                parameters=parameters,
            )
        )
        result.raise_for_status()
        result = PagedResponse[SpaceResponse].model_validate_json(result.success_response.body)
        return result.items
