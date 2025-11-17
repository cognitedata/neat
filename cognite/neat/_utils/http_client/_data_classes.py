import sys
from abc import ABC, abstractmethod
from collections import UserList
from collections.abc import MutableSequence, Sequence
from typing import Generic, Literal, TypeAlias, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_serializer

from cognite.neat._exceptions import CDFAPIException
from cognite.neat._utils.http_client._tracker import ItemsRequestTracker
from cognite.neat._utils.useful_types import PrimaryTypes, ReferenceObject, T_Reference

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

StatusCode: TypeAlias = int


class HTTPMessage(BaseModel):
    """Base class for HTTP messages (requests and responses)"""


class FailedRequestMessage(HTTPMessage):
    message: str

    def __str__(self) -> str:
        return self.message


class ResponseMessage(HTTPMessage):
    code: StatusCode
    body: str


class SuccessResponse(ResponseMessage): ...


class ErrorDetails(BaseModel):
    """This is the structure of failure responses from CDF APIs"""

    code: StatusCode
    message: str
    missing: list[JsonValue] | None = None
    duplicated: list[JsonValue] | None = None
    is_auto_retryable: bool | None = Field(None, alias="isAutoRetryable")

    @classmethod
    def from_response(cls, response: httpx.Response) -> "ErrorDetails":
        try:
            return _ErrorResponse.model_validate_json(response.text).error
        except ValidationError:
            return cls(code=response.status_code, message=response.text)


class _ErrorResponse(BaseModel):
    error: ErrorDetails


class FailedResponse(ResponseMessage):
    error: ErrorDetails

    def __str__(self) -> str:
        return f"HTTP {self.code} | {self.error.message}"


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


class SimpleRequest(RequestMessage):
    """Base class for requests with a simple success/fail response structure"""

    def create_success_response(self, response: httpx.Response) -> Sequence[HTTPMessage]:
        return [SuccessResponse(code=response.status_code, body=response.text)]

    def create_failure_response(self, response: httpx.Response) -> Sequence[HTTPMessage]:
        return [
            FailedResponse(code=response.status_code, body=response.text, error=ErrorDetails.from_response(response))
        ]

    def create_failed_request(self, error_message: str) -> Sequence[HTTPMessage]:
        return [FailedRequestMessage(message=error_message)]


class ParametersRequest(SimpleRequest):
    """Base class for HTTP request messages with query parameters"""

    parameters: dict[str, PrimaryTypes] | None = None


class BodyRequest(ParametersRequest, ABC):
    """Base class for HTTP request messages with a body"""

    @abstractmethod
    def data(self) -> str:
        raise NotImplementedError()


class SimpleBodyRequest(BodyRequest):
    body: str

    def data(self) -> str:
        return self.body


class ItemMessage(BaseModel, Generic[T_Reference], ABC):
    """Base class for message related to a specific item"""

    ids: Sequence[T_Reference]


class SuccessResponseItems(ItemMessage[T_Reference], SuccessResponse): ...


class FailedResponseItems(ItemMessage[T_Reference], FailedResponse): ...


class FailedRequestItems(ItemMessage[T_Reference], FailedRequestMessage): ...


T_BaseModel = TypeVar("T_BaseModel", bound=BaseModel)


class ItemBody(BaseModel, Generic[T_Reference, T_BaseModel], ABC):
    items: Sequence[T_BaseModel]
    extra_args: dict[str, JsonValue] | None = None

    @model_serializer(mode="plain", return_type=dict)
    def serialize(self) -> dict[str, JsonValue]:
        data: dict[str, JsonValue] = {
            "items": [item.model_dump(exclude_unset=False, by_alias=True, exclude_none=False) for item in self.items]
        }
        if isinstance(self.extra_args, dict):
            data.update(self.extra_args)
        return data

    @abstractmethod
    def as_ids(self) -> list[T_Reference]:
        """Returns the list of item identifiers for the items in the body."""
        raise NotImplementedError()

    def split(self, mid: int) -> tuple[Self, Self]:
        """Splits the body into two smaller bodies.

        This is useful for retrying requests that fail due to size limits or timeouts.

        Args:
            mid: The index at which to split the items.
        Returns:
            A tuple containing two new ItemBody instances, each with half of the original items.

        """

        type_ = type(self)
        return type_(items=self.items[:mid], extra_args=self.extra_args), type_(
            items=self.items[mid:], extra_args=self.extra_args
        )


class ItemIDBody(ItemBody[ReferenceObject, ReferenceObject]):
    def as_ids(self) -> list[ReferenceObject]:
        return list(self.items)


class ItemsRequest(BodyRequest, Generic[T_Reference, T_BaseModel]):
    """Requests message for endpoints that accept multiple items in a single request.

    This class provides functionality to split large requests into smaller ones, handle responses for each item,
    and manage errors effectively.

    Attributes:
        body (ItemBody): The body of the request containing the items to be processed.
        max_failures_before_abort (int): The maximum number of failed split requests before aborting further splits.

    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    body: ItemBody[T_Reference, T_BaseModel]
    max_failures_before_abort: int = 50
    tracker: ItemsRequestTracker | None = None

    def data(self) -> str:
        return self.body.model_dump_json(exclude_unset=True, by_alias=True)

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
        messages: list[ItemsRequest] = []
        for body in self.body.split(mid):
            item_request = ItemsRequest(
                endpoint_url=self.endpoint_url,
                method=self.method,
                body=body,
                connect_attempt=self.connect_attempt,
                read_attempt=self.read_attempt,
                status_attempt=status_attempts,
            )
            item_request.tracker = tracker
            messages.append(item_request)
        return messages

    def create_success_response(self, response: httpx.Response) -> Sequence[HTTPMessage]:
        return [SuccessResponseItems(code=response.status_code, body=response.text, ids=self.body.as_ids())]

    def create_failure_response(self, response: httpx.Response) -> Sequence[HTTPMessage]:
        """Creates response messages based on the HTTP response and the original request.

        Args:
            response: The HTTP response received from the server.
        Returns:
            A sequence of HTTPMessage instances representing the outcome for each item in the request.
        """
        return [
            FailedResponseItems(
                code=response.status_code,
                body=response.text,
                error=ErrorDetails.from_response(response),
                ids=self.body.as_ids(),
            )
        ]

    def create_failed_request(self, error_message: str) -> Sequence[HTTPMessage]:
        """Creates failed request messages for each item in the request.

        Args:
            error_message: The error message to include in the failed request messages.

        Returns:
            A sequence of HTTPMessage instances representing the failed request for each item.
        """
        return [FailedRequestItems(message=error_message, ids=self.body.as_ids())]


class APIResponse(UserList, MutableSequence[ResponseMessage | FailedRequestMessage]):
    def __init__(self, collection: Sequence[ResponseMessage | FailedRequestMessage] | None = None):
        super().__init__(collection or [])

    def raise_for_status(self) -> None:
        error_messages = [message for message in self.data if not isinstance(message, SuccessResponse)]
        if error_messages:
            raise CDFAPIException(error_messages)

    @property
    def success_response(self) -> SuccessResponse:
        success = [msg for msg in self.data if isinstance(msg, SuccessResponse)]
        if len(success) == 1:
            return success[0]
        elif success:
            raise ValueError("Multiple successful HTTP responses found in the messages.")
        else:
            raise ValueError("No successful HTTP response found in the messages.")
