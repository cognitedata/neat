import re
from abc import ABC
from typing import Literal, TypeVar

from pydantic import Field, Json, field_validator

from cognite.neat._utils.text import humanize_collection

from ._base import Resource, WriteableResource
from ._constants import (
    CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    DM_EXTERNAL_ID_PATTERN,
    DM_VERSION_PATTERN,
    FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS,
    FORBIDDEN_CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER,
    SPACE_FORMAT_PATTERN,
)
from ._references import ContainerReference, ViewReference
from ._view_property import (
    ConnectionRequestProperty,
    ConnectionResponseProperty,
    ViewCorePropertyRequest,
    ViewCorePropertyResponse,
)

KEY_PATTERN = re.compile(CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN)


class View(Resource, ABC):
    space: str = Field(
        description="Id of the space that the view belongs to.",
        min_length=1,
        max_length=43,
        pattern=SPACE_FORMAT_PATTERN,
    )
    external_id: str = Field(
        description="External-id of the view.",
        min_length=1,
        max_length=255,
        pattern=DM_EXTERNAL_ID_PATTERN,
    )
    version: str = Field(
        description="Version of the view.",
        max_length=43,
        pattern=DM_VERSION_PATTERN,
    )
    name: str | None = Field(
        default=None,
        description="name for the view.",
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        description="Description of the view.",
        max_length=1024,
    )
    filter: dict[str, Json] | None = Field(
        default=None,
        description="A filter Domain Specific Language (DSL) used to create advanced filter queries.",
    )
    implements: list[ViewReference] | None = Field(
        default=None,
        description="References to the views from where this view will inherit properties.",
    )

    @field_validator("external_id", mode="after")
    def check_forbidden_external_id_value(cls, val: str) -> str:
        """Check the external_id not present in forbidden set"""
        if val in FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS:
            raise ValueError(
                f"'{val}' is a reserved view External ID. Reserved External IDs are: "
                f"{humanize_collection(FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS)}"
            )
        return val


class ViewRequest(View):
    properties: dict[str, ViewCorePropertyRequest | ConnectionRequestProperty] = Field(
        description="View with included properties and expected edges, indexed by a unique space-local identifier."
    )

    @field_validator("properties", mode="after")
    def validate_properties_identifier(
        cls,
        val: dict[str, ViewCorePropertyRequest | ConnectionRequestProperty],
    ) -> dict[str, ViewCorePropertyRequest | ConnectionRequestProperty]:
        """Validate properties Identifier"""
        return _validate_properties_keys(val)


class ViewResponse(View, WriteableResource[ViewRequest]):
    properties: dict[str, ViewCorePropertyResponse | ConnectionResponseProperty] = Field(
        description="List of properties and connections included in this view."
    )

    created_time: int = Field(
        description="When the view was created. The number of milliseconds since 00:00:00 Thursday, 1 January 1970, "
        "Coordinated Universal Time (UTC), minus leap seconds."
    )
    last_updated_time: int = Field(
        description="When the view was last updated. The number of milliseconds since 00:00:00 Thursday, "
        "1 January 1970, Coordinated Universal Time (UTC), minus leap seconds."
    )
    writable: bool = Field(
        description="oes the view support write operations, i.e. is it writable? "
        "You can write to a view if the view maps all non-nullable properties."
    )
    queryable: bool = Field(
        description="Does the view support queries, i.e. is it queryable? You can query a view if "
        "it either has a filter or at least one property mapped to a container."
    )
    used_for: Literal["node", "edge", "all"] = Field(description="Should this operation apply to nodes, edges or both.")
    is_global: bool = Field(description="Is this a global view.")
    mapped_containers: list[ContainerReference] = Field(
        description="List of containers with properties mapped by this view."
    )

    @field_validator("properties", mode="after")
    def validate_properties_identifier(
        cls, val: dict[str, ViewCorePropertyResponse | ConnectionResponseProperty]
    ) -> dict[str, ViewCorePropertyResponse | ConnectionResponseProperty]:
        """Validate properties Identifier"""
        return _validate_properties_keys(val)

    def as_request(self) -> ViewRequest:
        dumped = self.model_dump(by_alias=True, exclude={"properties"})
        dumped["properties"] = {
            key: value.as_request().model_dump(by_alias=True)
            if isinstance(value, WriteableResource)
            else value.model_dump(by_alias=True)
            for key, value in self.properties.items()
        }
        return ViewRequest.model_validate(dumped)


T_Property = TypeVar("T_Property")


def _validate_properties_keys(properties: dict[str, T_Property]) -> dict[str, T_Property]:
    """Validate keys of a properties dictionary."""
    errors: list[str] = []
    for key in properties:
        if not KEY_PATTERN.match(key):
            errors.append(f"Property '{key}' does not match the required pattern: {KEY_PATTERN.pattern}")
        if key in FORBIDDEN_CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER:
            errors.append(
                f"'{key}' is a reserved property identifier. Reserved identifiers are: "
                f"{humanize_collection(FORBIDDEN_CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER)}"
            )
    if errors:
        raise ValueError("; ".join(errors))
    return properties
