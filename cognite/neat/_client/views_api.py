from __future__ import annotations

from collections.abc import Sequence

from pydantic import TypeAdapter

from cognite.neat._data_model.models.dms import ViewReference, ViewRequest, ViewResponse
from cognite.neat._utils.http_client import HTTPClient, SuccessResponse

from . import NeatClientConfig
from .api import Endpoint, NeatAPI
from .data_classes import PagedResponse
from .filters import ViewFilter


class ViewsAPI(NeatAPI):
    def __init__(self, neat_config: NeatClientConfig, http_client: HTTPClient) -> None:
        super().__init__(
            neat_config,
            http_client,
            endpoint_map={
                "apply": Endpoint("POST", "/models/views", item_limit=100),
                "retrieve": Endpoint("POST", "/models/views/byids", item_limit=100),
                "delete": Endpoint("POST", "/models/views/delete", item_limit=100),
                "list": Endpoint("GET", "/models/views", item_limit=1000),
            },
        )

    def _validate_page_response(self, response: SuccessResponse) -> PagedResponse[ViewResponse]:
        return PagedResponse[ViewResponse].model_validate_json(response.body)

    def _validate_id_response(self, response: SuccessResponse) -> list[ViewReference]:
        return TypeAdapter(list[ViewReference]).validate_json(response.body)

    def apply(self, items: Sequence[ViewRequest]) -> list[ViewResponse]:
        """Create or update views in CDF Project.

        Args:
            items: List of ViewRequest objects to create or update.
        Returns:
            List of ViewResponse objects.
        """
        return self._request_item_response(items, "apply")

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
        return self._request_item_response(
            items, "retrieve", extra_body={"includeInheritedProperties": include_inherited_properties}
        )

    def delete(self, items: list[ViewReference]) -> list[ViewReference]:
        """Delete views by their identifiers.

        Args:
            items: List of (space, external_id, version) tuples identifying the views to delete.

        Returns:
            List of ViewReference objects representing the deleted views.
        """
        return self._request_id_response(items, "delete")

    def list(
        self,
        space: str | None = None,
        all_versions: bool = False,
        include_inherited_properties: bool = True,
        include_global: bool = False,
        limit: int | None = 10,
    ) -> list[ViewResponse]:
        """List views in CDF Project.

        Args:
            space: If specified, only views in this space are returned.
            all_versions: If True, return all versions. If False, only return the latest version.
            include_inherited_properties: If True, include properties inherited from parent views.
            include_global: If True, include global views.
            limit: Maximum number of views to return. If None, return all views.

        Returns:
            List of ViewResponse objects.
        """
        filter = ViewFilter(
            space=space,
            all_versions=all_versions,
            include_inherited_properties=include_inherited_properties,
            include_global=include_global,
        )
        return self._list(limit=limit, params=filter.dump())
