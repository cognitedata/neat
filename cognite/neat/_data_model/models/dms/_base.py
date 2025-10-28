from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel
from pydantic.alias_generators import to_camel


class BaseModelObject(BaseModel, alias_generator=to_camel, extra="ignore"):
    """Base class for all object. This includes resources and nested objects."""

    ...


T_Item = TypeVar("T_Item", bound=BaseModelObject)


class ReferenceObject(BaseModelObject, frozen=True, populate_by_name=True):
    """Base class for all reference objects - these are identifiers."""

    ...


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


T_Reference = TypeVar("T_Reference", bound=ReferenceObject | str)


class APIResource(Generic[T_Reference], ABC):
    """Base class for all API data modeling resources."""

    @abstractmethod
    def as_reference(self) -> T_Reference:
        """Convert the resource to a reference object (identifier)."""
        raise NotImplementedError()
