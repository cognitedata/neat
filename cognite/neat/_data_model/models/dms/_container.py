import re
from abc import ABC
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.useful_types import BaseModelObject

from ._base import APIResource, Resource, WriteableResource
from ._constants import (
    CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    DM_EXTERNAL_ID_PATTERN,
    FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS,
    FORBIDDEN_CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER,
    SPACE_FORMAT_PATTERN,
)
from ._constraints import Constraint
from ._data_types import DataType
from ._indexes import Index
from ._references import ContainerReference

KEY_PATTERN = re.compile(CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN)


class ContainerPropertyDefinition(BaseModelObject):
    immutable: bool | None = Field(
        default=None,
        description="Should updates to this property be rejected after the initial population?",
    )
    nullable: bool | None = Field(
        default=None,
        description="Does this property need to be set to a value, or not?",
    )
    auto_increment: bool | None = Field(
        default=None,
        description="Increment the property based on its highest current value (max value).",
    )
    default_value: str | int | float | bool | dict[str, Any] | None = Field(
        default=None,
        description="Default value to use when you do not specify a value for the property.",
    )
    description: str | None = Field(
        default=None,
        description="Description of the content and suggested use for this property.",
        max_length=1024,
    )
    name: str | None = Field(
        default=None,
        description="Readable property name.",
        max_length=255,
    )
    type: DataType = Field(description="The type of data you can store in this property.")


class Container(Resource, APIResource[ContainerReference], ABC):
    space: str = Field(
        description="The workspace for the container, a unique identifier for the space.",
        min_length=1,
        max_length=43,
        pattern=SPACE_FORMAT_PATTERN,
    )
    external_id: str = Field(
        description="External-id of the container.",
        min_length=1,
        max_length=255,
        pattern=DM_EXTERNAL_ID_PATTERN,
    )
    name: str | None = Field(
        default=None,
        description="name for the container.",
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        description="Description of the container.",
        max_length=1024,
    )
    used_for: Literal["node", "edge", "all"] | None = Field(
        default=None,
        description="Should this operation apply to nodes, edges or both.",
    )
    properties: dict[str, ContainerPropertyDefinition] = Field(
        description="Set of properties to apply to the container.",
    )
    constraints: dict[str, Constraint] | None = Field(
        default=None,
        description="Set of constraints to apply to the container.",
        max_length=10,
    )
    indexes: dict[str, Index] | None = Field(
        default=None,
        description="Set of indexes to apply to the container.",
        max_length=10,
    )

    @field_validator("indexes", "constraints", mode="after")
    def validate_key_length(cls, val: dict[str, Any] | None, info: ValidationInfo) -> dict[str, Any] | None:
        """Validate keys"""
        if not isinstance(val, dict):
            return val
        invalid_keys = {key for key in val.keys() if not (1 <= len(key) <= 43)}
        if invalid_keys:
            raise ValueError(
                f"{info.field_name} keys must be between 1 and 43 characters long. Invalid keys: "
                f"{humanize_collection(invalid_keys)}"
            )
        return val

    @field_validator("properties", mode="after")
    def validate_property_keys(cls, val: dict[str, Any]) -> dict[str, Any]:
        """Validate property keys"""
        if invalid_keys := {key for key in val if not KEY_PATTERN.match(key)}:
            raise ValueError(
                f"Property keys must match pattern '{CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN}'. "
                f"Invalid keys: {humanize_collection(invalid_keys)}"
            )

        if forbidden_keys := set(val.keys()).intersection(FORBIDDEN_CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER):
            raise ValueError(
                f"Property keys cannot be any of the following reserved values: {humanize_collection(forbidden_keys)}"
            )
        return val

    @field_validator("external_id")
    def check_forbidden_external_id_value(cls, val: str) -> str:
        """Check the external_id not present in forbidden set"""
        if val in FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS:
            raise ValueError(
                f"{val!r} is a reserved container External ID. Reserved External IDs are: "
                f"{humanize_collection(FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS)}"
            )
        return val

    def as_reference(self) -> ContainerReference:
        return ContainerReference(
            space=self.space,
            external_id=self.external_id,
        )


class ContainerRequest(Container): ...


class ContainerResponse(Container, WriteableResource[ContainerRequest]):
    created_time: int = Field(
        description="When the container was created. The number of milliseconds since 00:00:00 "
        "Thursday, 1 January 1970, "
        "Coordinated Universal Time (UTC), minus leap seconds."
    )
    last_updated_time: int = Field(
        description="When the container was last updated. The number of milliseconds since 00:00:00 Thursday, "
        "1 January 1970, Coordinated Universal Time (UTC), minus leap seconds."
    )
    is_global: bool = Field(description="Whether the container is a global container.")

    def as_request(self) -> "ContainerRequest":
        return ContainerRequest.model_validate(self.model_dump(by_alias=True))
