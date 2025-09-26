from abc import ABC
from typing import Any, Literal

from pydantic import Field

from ._base import BaseModelObject, Resource, WriteableResource
from ._constants import CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN
from ._data_types import DataType
from ._references import ContainerReference, ViewReference


class ViewProperty(Resource, ABC):
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
    source: ViewReference | None = Field(
        default=None,
        description="Indicates on what type a referenced direct relation is expected to be. Only applicable for direct relation properties.",
    )


class ViewPropertyRequest(ViewProperty): ...


class ConstraintOrIndexState(BaseModelObject):
    nullability: Literal["current", "pending", "failed"] | None = Field(
        description="""For properties that have isNullable set to false, this field describes the validity of the not-null constraint. It is not specified for nullable properties.

Possible values are:

"failed": The property contains null values, violating the constraint. This can occur if a property with existing nulls was made non-nullable. New null values will still be rejected.
"current": The constraint is satisfied; all values in the property are not null.
"pending": The constraint validity has not yet been computed.
        """
    )


class ViewPropertyResponse(ViewProperty, WriteableResource[ViewPropertyRequest]):
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
    default_value: str | int | bool | dict[str, Any] | None = Field(
        default=None,
        description="Default value to use when you do not specify a value for the property.",
    )
    constraint_state: ConstraintOrIndexState = Field(
        description="Describes the validity of constraints defined on this property"
    )
    type: DataType = Field(description="The type of data you can store in this property.")

    def as_request(self) -> ViewPropertyRequest:
        return ViewPropertyRequest.model_validate(self.model_dump(by_alias=True))
