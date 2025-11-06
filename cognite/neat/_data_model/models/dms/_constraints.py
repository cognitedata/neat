from abc import ABC
from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter, field_serializer
from pydantic_core.core_schema import FieldSerializationInfo

from cognite.neat._utils.useful_types import BaseModelObject

from ._references import ContainerReference
from ._types import Bool


class ConstraintDefinition(BaseModelObject, ABC):
    constraint_type: str


class UniquenessConstraintDefinition(ConstraintDefinition):
    constraint_type: Literal["uniqueness"] = "uniqueness"
    properties: list[str] = Field(
        description="List of properties included in the constraint.", min_length=1, max_length=10
    )
    by_space: Bool | None = Field(default=None, description="Whether to make the constraint space-specific.")


class RequiresConstraintDefinition(ConstraintDefinition):
    constraint_type: Literal["requires"] = "requires"
    require: ContainerReference = Field(description="Reference to an existing container.")

    @field_serializer("require", mode="plain")
    @classmethod
    def serialize_require(cls, require: ContainerReference, info: FieldSerializationInfo) -> dict[str, Any]:
        output = require.model_dump(**vars(info))
        output["type"] = "container"
        return output


Constraint = Annotated[
    UniquenessConstraintDefinition | RequiresConstraintDefinition,
    Field(discriminator="constraint_type"),
]

ConstraintAdapter: TypeAdapter[Constraint] = TypeAdapter(Constraint)
