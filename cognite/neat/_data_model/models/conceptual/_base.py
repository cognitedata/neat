from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from cognite.neat._data_model._identifiers import URI


class BaseModelObject(BaseModel, alias_generator=to_camel, extra="ignore", populate_by_name=True):
    """Base class for all object. This includes resources and nested objects."""

    ...


class ResourceMetadata(BaseModelObject):
    name: str | None = Field(
        None, description="Human readable / display name of resource being described.", max_length=1024
    )
    description: str | None = Field(None, description="The description of the resource.", max_length=255)
    uri: URI | None = Field(None, description="The URI of the resource being described.")
