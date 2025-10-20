from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Generic, Literal, TypeAlias, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

from cognite.neat._utils.http_client._tracker import ItemsRequestTracker
from cognite.neat._utils.useful_types import T_ID, PrimaryTypes

StatusCode: TypeAlias = int

T_BaseModel = TypeVar("T_BaseModel", bound=BaseModel)


class HTTPMessage(BaseModel):
    """Base class for HTTP messages (requests and responses)"""


class FailedRequestMessage(HTTPMessage):
    message: str


class ResponseMessage(HTTPMessage):
    code: int


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
    def create_success_response(self, response: httpx.Response) -> Sequence[HTTPMessage]:
        raise NotImplementedError()

    @abstractmethod
    def create_failure_response(self, response: httpx.Response) -> Sequence[HTTPMessage]:
        raise NotImplementedError()

    @abstractmethod
    def create_failed_request(self, error_message: str) -> Sequence[HTTPMessage]:
        raise NotImplementedError()


class SuccessResponse(ResponseMessage):
    data: bytes


class ErrorDetails(BaseModel):
    code: int
    message: str
    missing: list[JsonValue] | None = None
    duplicated: list[JsonValue] | None = None

class ErrorResponse(BaseModel):
    error: ErrorDetails

class FailedResponse(ResponseMessage, ErrorResponse):
    ...


class SimpleRequest(RequestMessage):
    """Base class for requests with a simple success/fail response structure"""

    @classmethod
    def create_success_response(cls, response: httpx.Response) -> Sequence[ResponseMessage]:
        return [SuccessResponse(code=response.status_code, data=response.content)]

    @classmethod
    def create_failure_response(cls, response: httpx.Response) -> Sequence[ResponseMessage]:
        error = ErrorResponse.model_validate_json(response.content)
        return [FailedResponse(code=response.status_code, error=error.error)]

    @classmethod
    def create_failed_request(cls, error_message: str) -> Sequence[HTTPMessage]:
        return [FailedRequestMessage(message=error_message)]


class BodyRequest(RequestMessage, ABC):
    """Base class for HTTP request messages with a body"""

    @abstractmethod
    def data(self) -> str:
        raise NotImplementedError()


class ParametersRequest(SimpleRequest):
    """Base class for HTTP request messages with query parameters"""

    parameters: dict[str, PrimaryTypes] | None = None


class SimpleBodyRequest(SimpleRequest, BodyRequest):
    body: str

    def data(self) -> str:
        return self.body


class ItemMessage(BaseModel):
    """Base class for message related to a specific item"""

    ...


class ItemIDMessage(Generic[T_ID], ItemMessage, ABC):
    """Base class for message related to a specific item identified by an ID"""

    id: T_ID


class ItemResponse(ItemIDMessage, ResponseMessage, ABC): ...


class FailedItem(ItemResponse, FailedResponse): ...


class FailedRequestItem(ItemIDMessage, FailedRequestMessage): ...


class ItemBody(BaseModel, Generic[T_BaseModel]):
    model_config = ConfigDict(extra="allow")
    items: list[T_BaseModel]


class ItemsRequest(BodyRequest, Generic[T_ID, T_BaseModel]):
    """Requests message for endpoints that accept multiple items in a single request.

    This class provides functionality to split large requests into smaller ones, handle responses for each item,
    and manage errors effectively.

    Attributes:
        body (ItemBody[T_BaseModel]): The body of the request containing the items to be processed.
        as_id (Callable[[JsonVal], T_ID] | None): A function to extract the ID from each item. If None,
            IDs are not used.
        max_failures_before_abort (int): The maximum number of failed split requests before aborting further splits.

    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    body: ItemBody[T_BaseModel]
    as_id: Callable[[T_BaseModel], T_ID]
    max_failures_before_abort: int = 50
    tracker: ItemsRequestTracker | None = None

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

    def create_success_response(self, response: httpx.Response) -> Sequence[HTTPMessage]:
        """Creates response messages based on the HTTP response and the original request.

        Args:
            response: The HTTP response received from the server.

        Returns:
            A sequence of HTTPMessage instances representing the outcome for each item in the request.
        """
        return SimpleRequest.create_success_response(response)

    def create_failure_response(self, response: httpx.Response) -> Sequence[HTTPMessage]:
        """Creates response messages based on the HTTP response and the original request.

        Args:
            response: The HTTP response received from the server.
        Returns:
            A sequence of HTTPMessage instances representing the outcome for each item in the request.
        """
        responses: list[HTTPMessage] = []
        error = FailedResponse.model_validate_json(response.content).model_dump()
        for item in self.body.items:
            try:
                item_id = self.as_id(item)
            except Exception:
                raise ValueError("Invalid as_id function provided for ItemsRequest") from None
            responses.append(FailedItem(id=item_id, **error))
        return responses

    def create_failed_request(self, error_message: str) -> Sequence[HTTPMessage]:
        """Creates failed request messages for each item in the request.

        Args:
            error_message: The error message to include in the failed request messages.

        Returns:
            A sequence of HTTPMessage instances representing the failed request for each item.
        """
        responses: list[HTTPMessage] = []
        for item in self.body.items:
            try:
                item_id = self.as_id(item)
            except Exception:
                raise ValueError("Invalid as_id function provided for ItemsRequest") from None
            responses.append(FailedRequestItem(id=item_id, message=error_message))
        return responses
