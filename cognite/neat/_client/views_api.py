from __future__ import annotations

from collections.abc import Sequence

from cognite.neat._data_model.models.dms import DataModelBody, ViewReference, ViewRequest, ViewResponse
from cognite.neat._utils.collection import chunker_sequence
from cognite.neat._utils.http_client import ItemIDBody, ItemsRequest, ParametersRequest
from cognite.neat._utils.useful_types import PrimitiveType

from .api import NeatAPI
from .data_classes import PagedResponse


class ViewsAPI(NeatAPI):
    ENDPOINT = "/models/views"

    def apply(self, items: Sequence[ViewRequest]) -> list[ViewResponse]:
        """Create or update views in CDF Project.
        Args:
            items: List of ViewRequest objects to create or update.
        Returns:
            List of ViewResponse objects.
        """
        if not items:
            return []
        if len(items) > 100:
            raise ValueError("Cannot apply more than 100 views at once.")
        result = self._http_client.request_with_retries(
            ItemsRequest(
                endpoint_url=self._config.create_api_url(self.ENDPOINT),
                method="POST",
                body=DataModelBody(items=items),
            )
        )
        result.raise_for_status()
        result = PagedResponse[ViewResponse].model_validate_json(result.success_response.body)
        return result.items

    def retrieve(
        self,
        items: list[ViewReference],
        include_inherited_properties: bool = True,
    ) -> list[ViewResponse]:
        """Retrieve views by their identifiers.

        Args:
            items: List of (space, external_id, version) tuples identifying the views to retrieve.
            include_inherited_properties: If True, include properties inherited from parent views.

        Returns:
            List of ViewResponse objects.
        """
        results: list[ViewResponse] = []
        for chunk in chunker_sequence(items, 100):
            batch = self._http_client.request_with_retries(
                ItemsRequest(
                    endpoint_url=self._config.create_api_url(f"{self.ENDPOINT}/byids"),
                    method="POST",
                    body=ItemIDBody(items=chunk),
                    parameters={"includeInheritedProperties": include_inherited_properties},
                )
            )
            batch.raise_for_status()
            result = PagedResponse[ViewResponse].model_validate_json(batch.success_response.body)
            results.extend(result.items)
        return results

    def delete(self, items: list[ViewReference]) -> list[ViewReference]:
        """Delete views by their identifiers.

        Args:
            items: List of (space, external_id, version) tuples identifying the views to delete.
        """
        if not items:
            return []
        if len(items) > 100:
            raise ValueError("Cannot delete more than 100 views at once.")

        result = self._http_client.request_with_retries(
            ItemsRequest(
                endpoint_url=self._config.create_api_url(f"{self.ENDPOINT}/delete"),
                method="POST",
                body=ItemIDBody(items=items),
            )
        )
        result.raise_for_status()
        result = PagedResponse[ViewReference].model_validate_json(result.success_response.body)
        return result.items

    def list(
        self,
        space: str | None = None,
        all_versions: bool = False,
        include_inherited_properties: bool = True,
        include_global: bool = False,
        limit: int = 10,
    ) -> list[ViewResponse]:
        """List views in CDF Project.

        Args:
            space: If specified, only views in this space are returned.
            all_versions: If True, return all versions. If False, only return the latest version.
            include_inherited_properties: If True, include properties inherited from parent views.
            include_global: If True, include global views.
            limit: Maximum number of views to return. Max is 1000.

        Returns:
            List of ViewResponse objects.
        """
        if limit > 1000:
            raise ValueError("Pagination is not (yet) supported for listing views. The maximum limit is 1000.")
        parameters: dict[str, PrimitiveType] = {
            "allVersions": all_versions,
            "includeInheritedProperties": include_inherited_properties,
            "includeGlobal": include_global,
            "limit": limit,
        }
        if space is not None:
            parameters["space"] = space
        result = self._http_client.request_with_retries(
            ParametersRequest(
                endpoint_url=self._config.create_api_url(self.ENDPOINT),
                method="GET",
                parameters=parameters,
            )
        )
        result.raise_for_status()
        result = PagedResponse[ViewResponse].model_validate_json(result.success_response.body)
        return result.items
