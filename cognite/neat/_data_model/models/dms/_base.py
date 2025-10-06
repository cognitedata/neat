from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel
from pydantic.alias_generators import to_camel


class BaseModelObject(BaseModel, alias_generator=to_camel, extra="ignore"):
    """Base class for all object. This includes resources and nested objects."""

    ...


class Resource(BaseModelObject):
    """Base class for all data modeling resources."""

    ...


T_Resource = TypeVar("T_Resource", bound=Resource)


class WriteableResource(Resource, Generic[T_Resource], ABC):
    @abstractmethod
    def as_request(self) -> T_Resource:
        """Convert the response model to a request model by removing read-only fields."""
        raise NotImplementedError()
