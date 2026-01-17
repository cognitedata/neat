from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, JsonValue, TypeAdapter

from cognite.neat._client.config import NeatClientConfig
from cognite.neat._data_model.models.dms._base import T_Resource, T_Response
from cognite.neat._utils.collection import chunker_sequence
from cognite.neat._utils.http_client import HTTPClient, ParametersRequest, SimpleBodyRequest, SuccessResponse
from cognite.neat._utils.useful_types import T_Reference

from .data_classes import PagedResponse

_T_BaseModel = TypeVar("_T_BaseModel", bound=BaseModel)


@dataclass(frozen=True)
class Endpoint:
    method: Literal["GET", "POST"]
    path: str
    item_limit: int
    concurrency_max_workers: int = 1


APIMethod: TypeAlias = Literal["apply", "retrieve", "delete", "list"]


class NeatAPI(Generic[T_Reference, T_Resource, T_Response], ABC):
    def __init__(
        self, neat_config: NeatClientConfig, http_client: HTTPClient, endpoint_map: dict[APIMethod, Endpoint]
    ) -> None:
        self._config = neat_config
        self._http_client = http_client
        self._method_endpoint_map = endpoint_map

    @abstractmethod
    def _validate_page_response(self, response: SuccessResponse) -> PagedResponse[T_Response]:
        """Parse a single item response."""
        raise NotImplementedError()

    @abstractmethod
    def _validate_id_response(self, response: SuccessResponse) -> list[T_Reference]:
        """Parse a single item response."""
        raise NotImplementedError()

    def _make_url(self, path: str = "") -> str:
        """Create the full URL for this resource endpoint."""
        return self._config.create_api_url(path)

    def _request_item_response(
        self,
        items: Sequence[BaseModel],
        method: APIMethod,
        extra_body: dict[str, Any] | None = None,
    ) -> list[T_Response]:
        response_items: list[T_Response] = []
        for response in self._chunk_requests(items, method, extra_body):
            response_items.extend(self._validate_page_response(response).items)
        return response_items

    def _request_id_response(
        self,
        items: Sequence[BaseModel],
        method: APIMethod,
        extra_body: dict[str, Any] | None = None,
    ) -> list[T_Reference]:
        response_items: list[T_Reference] = []
        for response in self._chunk_requests(items, method, extra_body):
            response_items.extend(self._validate_id_response(response))
        return response_items

    def _chunk_requests(
        self,
        items: Sequence[_T_BaseModel],
        method: APIMethod,
        extra_body: dict[str, Any] | None = None,
    ) -> Iterable[SuccessResponse]:
        """Send requests in chunks and yield responses.

        Args:
            items: The items to process.
            method: The API method to use. This is used ot look the up the endpoint.
            extra_body: Optional extra body content to include in the request.

        Yields:
            The successful responses from the API.
        """
        # Filter out None
        endpoint = self._method_endpoint_map[method]

        for chunk in chunker_sequence(items, endpoint.item_limit):
            request = SimpleBodyRequest(
                endpoint_url=self._make_url(endpoint.path),
                method=endpoint.method,
                body=TypeAdapter(dict[str, JsonValue]).dump_json(
                    {
                        "items": [item.model_dump(by_alias=True, exclude_unset=True) for item in chunk],
                        **(extra_body or {}),
                    },
                ),
            )
            response = self._http_client.request_with_retries(request)
            response.raise_for_status()
            yield response.success_response

    @classmethod
    def _filter_out_none_values(cls, params: dict[str, Any] | None) -> dict[str, Any] | None:
        request_params: dict[str, Any] | None = None
        if params:
            request_params = {k: v for k, v in params.items() if v is not None}
        return request_params

    def _paginate(
        self,
        limit: int,
        cursor: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> PagedResponse[T_Response]:
        """Fetch a single page of resources.

        Args:
            params: Query parameters for the request. Supported parameters depend on
                the resource type but typically include:
                - cursor: Cursor for pagination
                - limit: Maximum number of items (defaults to list limit)
                - space: Filter by space
                - includeGlobal: Whether to include global resources
            limit: Maximum number of items to return in the page.
            cursor: Cursor for pagination.

        Returns:
            A Page containing the items and the cursor for the next page.
        """
        endpoint = self._method_endpoint_map["list"]
        if not (0 < limit <= endpoint.item_limit):
            raise ValueError(f"Limit must be between 1 and {endpoint.item_limit}, got {limit}.")
        if endpoint.method != "GET":
            raise NotImplementedError(f"Pagination not implemented for method {endpoint.method}.")
        request_params = self._filter_out_none_values(params) or {}
        request_params["limit"] = limit
        if cursor is not None:
            request_params["cursor"] = cursor
        request = ParametersRequest(
            endpoint_url=self._make_url(endpoint.path),
            method=endpoint.method,
            parameters=request_params,
        )
        result = self._http_client.request_with_retries(request)
        result.raise_for_status()
        return self._validate_page_response(result.success_response)

    def _iterate(
        self,
        limit: int | None = None,
        cursor: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Iterable[list[T_Response]]:
        """Iterate over all resources, handling pagination automatically."""
        next_cursor = cursor
        total = 0
        endpoint = self._method_endpoint_map["list"]
        while True:
            page_limit = endpoint.item_limit if limit is None else min(limit - total, endpoint.item_limit)
            page = self._paginate(limit=page_limit, cursor=next_cursor, params=params)
            yield page.items
            total += len(page.items)
            if page.next_cursor is None or (limit is not None and total >= limit):
                break
            next_cursor = page.next_cursor

    def _list(
        self,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[T_Response]:
        """List all resources, handling pagination automatically."""
        return [item for batch in self._iterate(limit=limit, params=params) for item in batch]
