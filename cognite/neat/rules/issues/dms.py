from abc import ABC
from dataclasses import dataclass
from typing import Any, ClassVar

from cognite.client.data_classes import data_modeling as dm

from .base import NeatValidationError


@dataclass(frozen=True)
class DMSSchemaError(NeatValidationError, ABC): ...


@dataclass(frozen=True)
class ChangingContainerError(DMSSchemaError):
    description = "You are adding to an existing model. "
    fix = "Keep the container the same"
    error_name: ClassVar[str] = "ChangingContainerError"
    container_id: dm.ContainerId
    changed_properties: list[str] | None = None
    changed_attributes: list[str] | None = None

    def __post_init__(self):
        # Sorting for deterministic output
        if self.changed_properties:
            self.changed_properties.sort()
        if self.changed_attributes:
            self.changed_attributes.sort()

    def message(self) -> str:
        if self.changed_properties:
            changed = f" properties {self.changed_properties}."
        elif self.changed_attributes:
            changed = f" attributes {self.changed_attributes}."
        else:
            changed = "."
        return (
            f"The container {self.container_id} has changed{changed}"
            "When extending model with extension set to addition or reshape, the container "
            "properties must remain the same"
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["container_id"] = self.container_id.dump()
        output["changed_properties"] = self.changed_properties
        return output


@dataclass(frozen=True)
class ChangingViewError(DMSSchemaError):
    description = "You are adding to an existing model. "
    fix = "Keep the view the same"
    error_name: ClassVar[str] = "ChangingViewError"
    view_id: dm.ViewId
    changed_properties: list[str] | None = None
    changed_attributes: list[str] | None = None

    def __post_init__(self):
        # Sorting for deterministic output
        if self.changed_properties:
            self.changed_properties.sort()
        if self.changed_attributes:
            self.changed_attributes.sort()

    def message(self) -> str:
        if self.changed_properties:
            changed = f" properties {self.changed_properties}."
        elif self.changed_attributes:
            changed = f" attributes {self.changed_attributes}."
        else:
            changed = "."

        return (
            f"The view {self.view_id} has changed{changed}"
            "When extending model with extension set to addition, the view properties must remain the same"
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = self.view_id.dump()
        output["difference"] = self.changed_properties
        return output
