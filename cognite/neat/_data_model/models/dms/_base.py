from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from cognite.neat._utils.useful_types import BaseModelObject, T_Reference


class Resource(BaseModelObject):
    """Base class for all data modeling resources."""

    ...


T_Resource = TypeVar("T_Resource", bound=Resource)


class WriteableResource(Resource, Generic[T_Resource], ABC):
    """Base class for all writeable data modeling resources."""

    @abstractmethod
    def as_request(self) -> T_Resource:
        """Convert the response model to a request model by removing read-only fields."""
        raise NotImplementedError()


class APIResource(Generic[T_Reference], ABC):
    """Base class for all API data modeling resources."""

    @abstractmethod
    def as_reference(self) -> T_Reference:
        """Convert the resource to a reference object (identifier)."""
        raise NotImplementedError()
