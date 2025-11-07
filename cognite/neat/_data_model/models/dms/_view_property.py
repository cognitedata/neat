from abc import ABC
from typing import Annotated, Any, Literal

from pydantic import Field, Json, TypeAdapter, field_serializer
from pydantic_core.core_schema import FieldSerializationInfo

from cognite.neat._utils.useful_types import BaseModelObject

from ._base import Resource, WriteableResource
from ._constants import CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN
from ._data_types import DataType
from ._references import ContainerDirectReference, ContainerReference, NodeReference, ViewDirectReference, ViewReference


class ViewPropertyDefinition(Resource, ABC):
    connection_type: str


class ViewCoreProperty(ViewPropertyDefinition, ABC):
    # Core properties do not have connection type in the API, but we add it here such that
    # we can use it as a discriminator in unions. The exclude=True ensures that it is not
    # sent to the API.
    connection_type: Literal["primary_property"] = Field(default="primary_property", exclude=True)
    name: str | None = Field(
        default=None,
        description="Readable property name.",
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        description="Description of the content and suggested use for this property..",
        max_length=1024,
    )
    container: ContainerReference = Field(
        description="Reference to the container where this property is defined.",
    )
    container_property_identifier: str = Field(
        description="Identifier of the property in the container.",
        min_length=1,
        max_length=255,
        pattern=CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    )

    @field_serializer("container", mode="plain")
    @classmethod
    def serialize_container(cls, container: ContainerReference, info: FieldSerializationInfo) -> dict[str, Any]:
        output = container.model_dump(**vars(info))
        output["type"] = "container"
        return output


class ViewCorePropertyRequest(ViewCoreProperty):
    source: ViewReference | None = Field(
        default=None,
        description="Indicates on what type a referenced direct relation is expected to be. "
        "Only applicable for direct relation properties.",
    )

    @field_serializer("source", mode="plain")
    @classmethod
    def serialize_source(cls, source: ViewReference | None, info: FieldSerializationInfo) -> dict[str, Any] | None:
        if source is None:
            return None
        output = source.model_dump(**vars(info))
        output["type"] = "view"
        return output


class ConstraintOrIndexState(BaseModelObject):
    nullability: Literal["current", "pending", "failed"] | None = Field(
        None,
        description="""For properties that have isNullable set to false, this field describes the validity of the
not-null constraint. It is not specified for nullable properties.

Possible values are:

"failed": The property contains null values, violating the constraint. This can occur if a property with
          existing nulls was made non-nullable. New null values will still be rejected.
"current": The constraint is satisfied; all values in the property are not null.
"pending": The constraint validity has not yet been computed.
        """,
    )


class ViewCorePropertyResponse(ViewCoreProperty, WriteableResource[ViewCorePropertyRequest]):
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
    default_value: str | int | bool | dict[str, Json] | None = Field(
        default=None,
        description="Default value to use when you do not specify a value for the property.",
    )
    constraint_state: ConstraintOrIndexState = Field(
        description="Describes the validity of constraints defined on this property"
    )
    type: DataType = Field(description="The type of data you can store in this property.")

    def as_request(self) -> ViewCorePropertyRequest:
        return ViewCorePropertyRequest.model_validate(self.model_dump(by_alias=True))


class ConnectionPropertyDefinition(ViewPropertyDefinition, ABC):
    name: str | None = Field(
        default=None,
        description="Readable property name.",
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        description="Description of the content and suggested use for this property..",
        max_length=1024,
    )


class EdgeProperty(ConnectionPropertyDefinition, ABC):
    source: ViewReference = Field(
        description="The target node(s) of this connection can be read through the view specified in 'source'."
    )
    type: NodeReference = Field(
        description="Reference to the node pointed to by the direct relation. The reference consists of a "
        "space and an external-id."
    )
    edge_source: ViewReference | None = Field(
        None, description="The edge(s) of this connection can be read through the view specified in 'edgeSource'."
    )
    direction: Literal["outwards", "inwards"] = Field(
        "outwards", description="The direction of the edge(s) of this connection."
    )

    @field_serializer("source", "edge_source", mode="plain")
    @classmethod
    def serialize_source(cls, source: ViewReference | None, info: FieldSerializationInfo) -> dict[str, Any] | None:
        if source is None:
            return None
        output = source.model_dump(**vars(info))
        output["type"] = "view"
        return output


class SingleEdgeProperty(EdgeProperty):
    connection_type: Literal["single_edge_connection"] = "single_edge_connection"


class MultiEdgeProperty(EdgeProperty):
    connection_type: Literal["multi_edge_connection"] = "multi_edge_connection"


class ReverseDirectRelationProperty(ConnectionPropertyDefinition, ABC):
    source: ViewReference = Field(
        description="The node(s) containing the direct relation property can be read "
        "through the view specified in 'source'."
    )
    through: ContainerDirectReference | ViewDirectReference = Field(
        description="The view of the node containing the direct relation property."
    )

    @field_serializer("source", mode="plain")
    @classmethod
    def serialize_source(cls, source: ViewReference, info: FieldSerializationInfo) -> dict[str, Any] | None:
        output = source.model_dump(**vars(info))
        output["type"] = "view"
        return output

    @field_serializer("through", mode="plain")
    @classmethod
    def serialize_through(
        cls, through: ContainerDirectReference | ViewDirectReference, info: FieldSerializationInfo
    ) -> dict[str, Any]:
        output = through.model_dump(**vars(info))
        if isinstance(through, ContainerDirectReference):
            output["source"]["type"] = "container"
        else:
            output["source"]["type"] = "view"
        return output


class SingleReverseDirectRelationPropertyRequest(ReverseDirectRelationProperty):
    connection_type: Literal["single_reverse_direct_relation"] = "single_reverse_direct_relation"


class MultiReverseDirectRelationPropertyRequest(ReverseDirectRelationProperty):
    connection_type: Literal["multi_reverse_direct_relation"] = "multi_reverse_direct_relation"


class SingleReverseDirectRelationPropertyResponse(
    ReverseDirectRelationProperty, WriteableResource[SingleReverseDirectRelationPropertyRequest]
):
    connection_type: Literal["single_reverse_direct_relation"] = "single_reverse_direct_relation"
    targets_list: bool = Field(
        description="Whether or not this reverse direct relation targets a list of direct relations.",
    )

    def as_request(self) -> SingleReverseDirectRelationPropertyRequest:
        return SingleReverseDirectRelationPropertyRequest.model_validate(self.model_dump(by_alias=True))


class MultiReverseDirectRelationPropertyResponse(
    ReverseDirectRelationProperty, WriteableResource[MultiReverseDirectRelationPropertyRequest]
):
    connection_type: Literal["multi_reverse_direct_relation"] = "multi_reverse_direct_relation"
    targets_list: bool = Field(
        description="Whether or not this reverse direct relation targets a list of direct relations.",
    )

    def as_request(self) -> MultiReverseDirectRelationPropertyRequest:
        return MultiReverseDirectRelationPropertyRequest.model_validate(self.model_dump(by_alias=True))


ViewRequestProperty = Annotated[
    SingleEdgeProperty
    | MultiEdgeProperty
    | SingleReverseDirectRelationPropertyRequest
    | MultiReverseDirectRelationPropertyRequest
    | ViewCorePropertyRequest,
    Field(discriminator="connection_type"),
]
ViewResponseProperty = Annotated[
    SingleEdgeProperty
    | MultiEdgeProperty
    | SingleReverseDirectRelationPropertyResponse
    | MultiReverseDirectRelationPropertyResponse
    | ViewCorePropertyResponse,
    Field(discriminator="connection_type"),
]

ViewRequestPropertyAdapter: TypeAdapter[ViewRequestProperty] = TypeAdapter(ViewRequestProperty)
