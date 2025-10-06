from abc import ABC
from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter, field_validator

from ._base import BaseModelObject
from ._references import ContainerReference


class ConstraintDefinition(BaseModelObject, ABC):
    constraint_type: str


class UniquenessConstraintDefinition(ConstraintDefinition):
    constraint_type: Literal["uniqueness"] = "uniqueness"
    properties: list[str] = Field(
        description="List of properties included in the constraint.", min_length=1, max_length=10
    )
    by_space: bool | None = Field(default=None, description="Whether to make the constraint space-specific.")

    @field_validator("by_space", mode="before")
    def string_to_bool(cls, value: Any) -> Any:
        if isinstance(value, str):
            if value.lower() in {"true", "yes", "1"}:
                return True
            elif value.lower() in {"false", "no", "0"}:
                return False
        return value


class RequiresConstraintDefinition(ConstraintDefinition):
    constraint_type: Literal["requires"] = "requires"
    require: ContainerReference = Field(description="Reference to an existing container.")


Constraint = Annotated[
    UniquenessConstraintDefinition | RequiresConstraintDefinition,
    Field(discriminator="constraint_type"),
]

ConstraintAdapter: TypeAdapter[Constraint] = TypeAdapter(Constraint)
