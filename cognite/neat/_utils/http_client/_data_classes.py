from abc import ABC, abstractmethod
from collections import UserList
from collections.abc import Callable, MutableSequence, Sequence
from dataclasses import dataclass, field
from typing import Generic, Literal, TypeAlias, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict

from cognite.neat._utils.http_client._tracker import ItemsRequestTracker
from cognite.neat._utils.useful_types import T_ID, JsonVal, PrimitiveType

StatusCode: TypeAlias = int

T_BaseModel = TypeVar("T_BaseModel", bound=BaseModel)


@dataclass
class HTTPMessage:
    """Base class for HTTP messages (requests and responses)"""

    ...


@dataclass
class FailedRequestMessage(HTTPMessage):
    error: str


@dataclass
class ResponseMessage(HTTPMessage):
    status_code: StatusCode


@dataclass
class RequestMessage(HTTPMessage, ABC):
    """Base class for HTTP request messages"""

    endpoint_url: str
    method: Literal["GET", "POST", "PATCH", "DELETE"]
    connect_attempt: int = 0
    read_attempt: int = 0
    status_attempt: int = 0
    api_version: str | None = None

    @property
    def total_attempts(self) -> int:
        return self.connect_attempt + self.read_attempt + self.status_attempt

    @abstractmethod
    def create_success_responses(self, response: httpx.Response) -> Sequence[HTTPMessage]:
        raise NotImplementedError()

    @abstractmethod
    def create_failed_responses(self, response: httpx.Response) -> Sequence[HTTPMessage]:
        raise NotImplementedError()

    @abstractmethod
    def create_failed_request(self, error_message: str) -> Sequence[HTTPMessage]:
        raise NotImplementedError()


@dataclass
class SuccessResponse(ResponseMessage):
    httpx_response: httpx.Response


@dataclass
class FailedResponse(ResponseMessage):
    httpx_response: httpx.Response


@dataclass
class SimpleRequest(RequestMessage):
    """Base class for requests with a simple success/fail response structure"""

    @classmethod
    def create_success_responses(cls, response: httpx.Response) -> Sequence[ResponseMessage]:
        return [SuccessResponse(status_code=response.status_code, httpx_response=response)]

    @classmethod
    def create_failed_responses(cls, response: httpx.Response) -> Sequence[ResponseMessage]:
        return [FailedResponse(status_code=response.status_code, httpx_response=response)]

    @classmethod
    def create_failed_request(cls, error_message: str) -> Sequence[HTTPMessage]:
        return [FailedRequestMessage(error=error_message)]


@dataclass
class BodyRequest(RequestMessage, ABC):
    """Base class for HTTP request messages with a body"""

    @abstractmethod
    def data(self) -> str:
        raise NotImplementedError()


@dataclass
class ParameterRequest(SimpleRequest):
    """Base class for HTTP request messages with query parameters"""

    parameters: dict[str, PrimitiveType] | None = None


@dataclass
class ItemMessage:
    """Base class for message related to a specific item"""

    ...


@dataclass
class ItemIDMessage(Generic[T_ID], ItemMessage, ABC):
    """Base class for message related to a specific item identified by an ID"""

    id: T_ID


@dataclass
class ItemResponse(ItemIDMessage, ResponseMessage, ABC): ...


@dataclass
class SuccessItem(ItemResponse):
    item: JsonVal | None = None


@dataclass
class FailedItem(ItemResponse):
    error: str


@dataclass
class MissingItem(ItemResponse): ...


@dataclass
class UnexpectedItem(ItemResponse):
    item: JsonVal | None = None


@dataclass
class FailedRequestItem(ItemIDMessage, FailedRequestMessage): ...


@dataclass
class UnknownRequestItem(ItemMessage, FailedRequestMessage):
    item: JsonVal | None = None


@dataclass
class UnknownResponseItem(ItemMessage, ResponseMessage):
    error: str
    item: JsonVal | None = None


class ItemBody(BaseModel, Generic[T_BaseModel]):
    model_config = ConfigDict(extra="allow")
    items: list[T_BaseModel] = field(default_factory=list)


@dataclass
class ItemsRequest(Generic[T_ID, T_BaseModel], BodyRequest):
    """Requests message for endpoints that accept multiple items in a single request.

    This class provides functionality to split large requests into smaller ones, handle responses for each item,
    and manage errors effectively.

    Attributes:
        body (ItemBody[T_BaseModel]): The body of the request containing the items.
        as_id (Callable[[JsonVal], T_ID] | None): A function to extract the ID from each item. If None,
            IDs are not used.
        max_failures_before_abort (int): The maximum number of failed split requests before aborting further splits.

    """

    body: ItemBody[T_BaseModel] = field(default_factory=lambda: ItemBody())
    as_id: Callable[[T_BaseModel], T_ID] | None = None
    max_failures_before_abort: int = 50
    tracker: ItemsRequestTracker | None = field(default=None, init=False)

    def data(self) -> str:
        return self.body.model_dump_json()

    def split(self, status_attempts: int) -> "list[ItemsRequest]":
        """Splits the request into two smaller requests.

        This is useful for retrying requests that fail due to size limits or timeouts.

        Args:
            status_attempts: The number of status attempts to set for the new requests. This is used when the
                request failed with a 5xx status code and we want to track the number of attempts. For 4xx errors,
                there is at least one item causing the error, so we do not increment the status attempts, but
                instead essentially do a binary search to find the problematic item(s).

        Returns:
            A list containing two new ItemsRequest instances, each with half of the original items.

        """
        mid = len(self.body.items) // 2
        if mid == 0:
            return [self]
        tracker = self.tracker or ItemsRequestTracker(self.max_failures_before_abort)
        tracker.register_failure()
        first_half = ItemsRequest[T_ID, T_BaseModel](
            endpoint_url=self.endpoint_url,
            method=self.method,
            body=ItemBody(items=self.body.items[:mid], **self.body.model_dump(exclude={"items"})),
            as_id=self.as_id,
            connect_attempt=self.connect_attempt,
            read_attempt=self.read_attempt,
            status_attempt=status_attempts,
        )
        first_half.tracker = tracker
        second_half = ItemsRequest[T_ID, T_BaseModel](
            endpoint_url=self.endpoint_url,
            method=self.method,
            body=ItemBody(items=self.body.items[mid:], **self.body.model_dump(exclude={"items"})),
            as_id=self.as_id,
            connect_attempt=self.connect_attempt,
            read_attempt=self.read_attempt,
            status_attempt=status_attempts,
        )
        second_half.tracker = tracker
        return [first_half, second_half]

    def create_success_responses(self, response: httpx.Response) -> Sequence[HTTPMessage]:
        """Creates response messages based on the HTTP response and the original request.

        Args:
            response: The HTTP response received from the server.

        Returns:
            A sequence of HTTPMessage instances representing the outcome for each item in the request.
        """
        if self.as_id is None:
            return SimpleRequest.create_success_responses(response)
        request_items_by_id, errors = self._create_items_by_id()
        responses: list[HTTPMessage] = list(errors)
        error_message = error_message or "Unknown error"

        if not self._is_items_response(response_body):
            return self._handle_non_items_response(responses, response, error_message, request_items_by_id)

        # Process items from response
        if response_body is not None:
            self._process_response_items(responses, response, response_body, error_message, request_items_by_id)

        # Handle missing items
        self._handle_missing_items(responses, response, request_items_by_id)

        return responses

    @staticmethod
    def _handle_non_items_response(
        responses: list[HTTPMessage],
        response: httpx.Response,
        error_message: str,
        request_items_by_id: dict[T_ID, JsonVal],
    ) -> list[HTTPMessage]:
        """Handles responses that do not contain an 'items' field in the body."""
        if 200 <= response.status_code < 300:
            responses.extend(
                SuccessItem(status_code=response.status_code, id=id_) for id_ in request_items_by_id.keys()
            )
        else:
            responses.extend(
                FailedItem(status_code=response.status_code, error=error_message, id=id_)
                for id_ in request_items_by_id.keys()
            )
        return responses

    def _process_response_items(
        self,
        responses: list[HTTPMessage],
        response: httpx.Response,
        response_body: dict[str, JsonVal],
        error_message: str,
        request_items_by_id: dict[T_ID, JsonVal],
    ) -> None:
        """Processes each item in the response body and categorizes them based on their status."""
        for response_item in response_body["items"]:  # type: ignore[union-attr]
            try:
                item_id = self.as_id(response_item)  # type: ignore[misc]
            except Exception as e:
                responses.append(
                    UnknownResponseItem(
                        status_code=response.status_code, item=response_item, error=f"Error extracting ID: {e!s}"
                    )
                )
                continue
            request_item = request_items_by_id.pop(item_id, None)
            if request_item is None:
                responses.append(UnexpectedItem(status_code=response.status_code, id=item_id, item=response_item))
            elif 200 <= response.status_code < 300:
                responses.append(SuccessItem(status_code=response.status_code, id=item_id, item=response_item))
            else:
                responses.append(FailedItem(status_code=response.status_code, id=item_id, error=error_message))

    @staticmethod
    def _handle_missing_items(
        responses: list[HTTPMessage], response: httpx.Response, request_items_by_id: dict[T_ID, JsonVal]
    ) -> None:
        """Handles items that were in the request but not present in the response."""
        for item_id in request_items_by_id.keys():
            responses.append(MissingItem(status_code=response.status_code, id=item_id))

    def create_failed_request(self, error_message: str) -> Sequence[HTTPMessage]:
        if self.as_id is None:
            return SimpleRequest.create_failed_request(error_message)
        items_by_id, errors = self._create_items_by_id()
        results: list[HTTPMessage] = []
        results.extend(errors)
        results.extend(FailedRequestItem(id=item_id, error=error_message) for item_id in items_by_id.keys())
        return results

    def _create_items_by_id(self) -> tuple[dict[T_ID, JsonVal], list[FailedRequestItem | UnknownRequestItem]]:
        if self.as_id is None:
            raise ValueError("as_id function must be provided to create items by ID")
        items_by_id: dict[T_ID, JsonVal] = {}
        errors: list[FailedRequestItem | UnknownRequestItem] = []
        for item in self.items:
            try:
                item_id = self.as_id(item)
            except Exception as e:
                errors.append(UnknownRequestItem(error=f"Error extracting ID: {e!s}", item=item))
                continue
            if item_id in items_by_id:
                errors.append(FailedRequestItem(id=item_id, error=f"Duplicate item ID: {item_id!r}"))
            else:
                items_by_id[item_id] = item
        return items_by_id, errors

    @staticmethod
    def _is_items_response(body: dict[str, JsonVal] | None = None) -> bool:
        if body is None:
            return False
        if "items" not in body:
            return False
        if not isinstance(body["items"], list):
            return False
        return True


class ResponseResult(UserList, MutableSequence[ResponseMessage | FailedRequestMessage]):
    def __init__(self, collection: Sequence[ResponseMessage | FailedRequestMessage] | None = None):
        super().__init__(collection or [])

    def raise_for_status(self) -> None:
        error_messages = [message for message in self.data if not isinstance(message, SuccessResponse)]
        if error_messages:
            raise Exception(f"One or more requests failed: {error_messages}")

    @property
    def httpx_response(self) -> httpx.Response:
        success = [msg for msg in self.data if isinstance(msg, SuccessResponse)]
        if len(success) == 1:
            return success[0].httpx_response
        elif success:
            raise ValueError("Multiple successful HTTP responses found in the messages.")
        else:
            raise ValueError("No successful HTTP response found in the messages.")
