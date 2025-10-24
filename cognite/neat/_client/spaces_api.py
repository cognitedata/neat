from __future__ import annotations

import json

from cognite.neat._data_model.models.dms import SpaceResponse
from cognite.neat._utils.http_client import ParametersRequest, SimpleBodyRequest
from cognite.neat._utils.useful_types import PrimitiveType

from cognite.neat._data_model.models.dms import ViewResponse


from .api import NeatAPI
from .data_classes import PagedResponse


class SpacesAPI(NeatAPI):
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
        result = PagedResponse[SpaceResponse].model_validate_json(result.success_response.data)
        return result.items

    def retrieve(
        self,
        spaces: list[str],
    ) -> list[SpaceResponse]:
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

        body = {
            "items": [{"space": space} for space in spaces],
        }

        result = self._http_client.request_with_retries(
            SimpleBodyRequest(
                endpoint_url=self._config.create_api_url("/models/spaces/byids"),
                method="POST",
                body=self._dump_json(body),
            )
        )
        result.raise_for_status()
        result = PagedResponse[SpaceResponse].model_validate_json(result.success_response.data)
        return result.items

    @staticmethod
    def _dump_json(data: dict) -> str:
        return json.dumps(data)



class ViewsAPI(NeatAPI):
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
                endpoint_url=self._config.create_api_url("/models/views"),
                method="GET",
                parameters=parameters,
            )
        )
        result.raise_for_status()
        result = PagedResponse[ViewResponse].model_validate_json(result.success_response.data)
        return result.items

    def retrieve(
        self,
        items: list[tuple[str, str, str]],
        include_inherited_properties: bool = True,
    ) -> list[ViewResponse]:
        """Retrieve views by their identifiers.

        Args:
            items: List of (space, external_id, version) tuples identifying the views to retrieve.
            include_inherited_properties: If True, include properties inherited from parent views.

        Returns:
            List of ViewResponse objects.
        """
        if not items:
            return []
        if len(items) > 1000:
            raise ValueError("Cannot retrieve more than 1000 views at once.")

        body = {
            "items": [
                {"space": space, "externalId": external_id, "version": version} for space, external_id, version in items
            ],
            "includeInheritedProperties": include_inherited_properties,
        }

        result = self._http_client.request_with_retries(
            SimpleBodyRequest(
                endpoint_url=self._config.create_api_url("/models/views/byids"),
                method="POST",
                body=self._dump_json(body),
            )
        )
        result.raise_for_status()
        result = PagedResponse[ViewResponse].model_validate_json(result.success_response.data)
        return result.items

    @staticmethod
    def _dump_json(data: dict) -> str:
        import json

        return json.dumps(data)
