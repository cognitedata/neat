from abc import ABC
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from ._base import BaseModelObject
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


Constraint = Annotated[
    UniquenessConstraintDefinition | RequiresConstraintDefinition,
    Field(discriminator="constraint_type"),
]

ConstraintAdapter: TypeAdapter[Constraint] = TypeAdapter(Constraint)
