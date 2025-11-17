from abc import ABC
from typing import Any

from pydantic import Field, field_serializer
from pydantic_core.core_schema import FieldSerializationInfo

from ._base import APIResource, Resource, WriteableResource
from ._constants import (
    DM_EXTERNAL_ID_PATTERN,
    DM_VERSION_PATTERN,
    SPACE_FORMAT_PATTERN,
)
from ._references import DataModelReference, ViewReference


class DataModel(Resource, APIResource[DataModelReference], ABC):
    """Cognite Data Model resource.

    Data models group and structure views into reusable collections.
    A data model contains a set of views where the node types can
    refer to each other with direct relations and edges.
    """

    space: str = Field(
        description="The workspace for the data model, a unique identifier for the space.",
        min_length=1,
        max_length=43,
        pattern=SPACE_FORMAT_PATTERN,
    )
    external_id: str = Field(
        description="External-id of the data model.",
        min_length=1,
        max_length=255,
        pattern=DM_EXTERNAL_ID_PATTERN,
    )
    version: str = Field(
        description="Version of the data model.",
        max_length=43,
        pattern=DM_VERSION_PATTERN,
    )
    name: str | None = Field(
        default=None,
        description="Human readable name for the data model.",
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        description="Description of the data model.",
        max_length=1024,
    )
    # The API supports View here, but in Neat we will only use ViewReference
    views: list[ViewReference] | None = Field(
        description="List of views included in this data model.",
        default=None,
    )

    def as_reference(self) -> DataModelReference:
        return DataModelReference(
            space=self.space,
            external_id=self.external_id,
            version=self.version,
        )

    @field_serializer("views", mode="plain")
    @classmethod
    def serialize_views(
        cls, views: list[ViewReference] | None, info: FieldSerializationInfo
    ) -> list[dict[str, Any]] | None:
        if views is None:
            return None
        output: list[dict[str, Any]] = []
        for view in views:
            dumped = view.model_dump(**vars(info))
            dumped["type"] = "view"
            output.append(dumped)
        return output


class DataModelRequest(DataModel): ...


class DataModelResponse(DataModel, WriteableResource[DataModelRequest]):
    created_time: int = Field(
        description="When the data model was created. The number of milliseconds since 00:00:00 Thursday, "
        "1 January 1970, Coordinated Universal Time (UTC), minus leap seconds."
    )
    last_updated_time: int = Field(
        description="When the data model was last updated. The number of milliseconds since 00:00:00 Thursday, "
        "1 January 1970, Coordinated Universal Time (UTC), minus leap seconds."
    )
    is_global: bool = Field(description="Is this a global data model.")

    def as_request(self) -> DataModelRequest:
        return DataModelRequest.model_validate(self.model_dump(by_alias=True))
