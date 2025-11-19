import re
from abc import ABC
from typing import Any, Literal, TypeVar

from pydantic import Field, JsonValue, field_serializer, field_validator, model_validator
from pydantic_core.core_schema import FieldSerializationInfo

from cognite.neat._utils.text import humanize_collection

from . import DirectNodeRelation
from ._base import APIResource, Resource, WriteableResource
from ._constants import (
    CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    DM_EXTERNAL_ID_PATTERN,
    DM_VERSION_PATTERN,
    FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS,
    FORBIDDEN_CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER,
    SPACE_FORMAT_PATTERN,
)
from ._references import ContainerReference, NodeReference, ViewReference
from ._view_property import (
    EdgeProperty,
    ViewCorePropertyResponse,
    ViewRequestProperty,
    ViewResponseProperty,
)

KEY_PATTERN = re.compile(CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN)


class View(Resource, APIResource[ViewReference], ABC):
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
    filter: dict[str, JsonValue] | None = Field(
        default=None,
        description="A filter Domain Specific Language (DSL) used to create advanced filter queries.",
    )
    implements: list[ViewReference] | None = Field(
        default=None,
        description="References to the views from where this view will inherit properties.",
    )

    def as_reference(self) -> ViewReference:
        return ViewReference(space=self.space, external_id=self.external_id, version=self.version)

    @model_validator(mode="before")
    def set_connection_type_on_primary_properties(cls, data: dict) -> dict:
        if "properties" not in data:
            return data
        properties = data["properties"]
        if not isinstance(properties, dict):
            return data
        # We assume all properties without connectionType are core properties.
        # The reason we set connectionType it easy for pydantic to discriminate the union.
        # This also leads to better error messages, as if there is a union and pydantic do not know which
        # type to pick it will give errors from all type in the union.
        new_properties: dict[str, Any] = {}
        for prop_id, prop in properties.items():
            if isinstance(prop, dict) and "connectionType" not in prop:
                prop_copy = prop.copy()
                prop_copy["connectionType"] = "primary_property"
                new_properties[prop_id] = prop_copy
            else:
                new_properties[prop_id] = prop
        if new_properties:
            new_data = data.copy()
            new_data["properties"] = new_properties
            return new_data

        return data

    @field_validator("external_id", mode="after")
    def check_forbidden_external_id_value(cls, val: str) -> str:
        """Check the external_id not present in forbidden set"""
        if val in FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS:
            raise ValueError(
                f"'{val}' is a reserved view External ID. Reserved External IDs are: "
                f"{humanize_collection(FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS)}"
            )
        return val

    @field_serializer("implements", mode="plain")
    @classmethod
    def serialize_implements(
        cls, implements: list[ViewReference] | None, info: FieldSerializationInfo
    ) -> list[dict[str, Any]] | None:
        if implements is None:
            return None
        output: list[dict[str, Any]] = []
        for view in implements:
            dumped = view.model_dump(**vars(info))
            dumped["type"] = "view"
            output.append(dumped)
        return output


class ViewRequest(View):
    properties: dict[str, ViewRequestProperty] = Field(
        description="View with included properties and expected edges, indexed by a unique space-local identifier."
    )

    @field_validator("properties", mode="after")
    def validate_properties_identifier(cls, val: dict[str, ViewRequestProperty]) -> dict[str, ViewRequestProperty]:
        """Validate properties Identifier"""
        return _validate_properties_keys(val)


class ViewResponse(View, WriteableResource[ViewRequest]):
    properties: dict[str, ViewResponseProperty] = Field(
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
    def validate_properties_identifier(cls, val: dict[str, ViewResponseProperty]) -> dict[str, ViewResponseProperty]:
        """Validate properties Identifier"""
        return _validate_properties_keys(val)

    @property
    def node_types(self) -> list[NodeReference]:
        """Get all node types referenced by this view."""
        nodes_refs: set[NodeReference] = set()
        for prop in self.properties.values():
            if isinstance(prop, EdgeProperty):
                nodes_refs.add(prop.type)
        return list(nodes_refs)

    def as_request(self) -> ViewRequest:
        dumped = self.model_dump(by_alias=True, exclude={"properties"})
        properties: dict[str, Any] = {}
        for key, value in self.properties.items():
            if isinstance(value, ViewCorePropertyResponse) and isinstance(value.type, DirectNodeRelation):
                # Special case. In the request the source of DirectNodeRelation is set on the Property object,
                # while in the response it is set on the DirectNodeRelation object.
                request_object = value.as_request().model_dump(by_alias=True)
                request_object["source"] = value.type.source.model_dump(by_alias=True) if value.type.source else None
                properties[key] = request_object
            elif isinstance(value, WriteableResource):
                properties[key] = value.as_request().model_dump(by_alias=True)
            else:
                properties[key] = value.model_dump(by_alias=True)

        dumped["properties"] = properties
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
