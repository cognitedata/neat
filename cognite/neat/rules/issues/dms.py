from abc import ABC
from dataclasses import dataclass
from typing import Any, ClassVar

from cognite.client.data_classes import data_modeling as dm

from .base import NeatValidationError, ValidationWarning


@dataclass(frozen=True)
class DMSSchemaError(NeatValidationError, ABC): ...


@dataclass(frozen=True)
class DMSSchemaWarning(ValidationWarning, ABC): ...


@dataclass(frozen=True)
class ViewSizeWarning(DMSSchemaWarning):
    description = (
        "The number of properties in the {view} view is {count} which is more than "
        "the recommended limit of {limit} properties. This can lead to performance issues."
    )
    fix = "Reduce the size of the view"
    error_name: ClassVar[str] = "ViewSizeWarning"

    view_id: dm.ViewId
    limit: int
    count: int

    def message(self) -> str:
        return self.description.format(view=repr(self.view_id), count=self.count, limit=self.limit)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = self.view_id.dump()
        output["limit"] = self.limit
        output["count"] = self.count
        return output


@dataclass(frozen=True)
class IncompleteSchemaError(DMSSchemaError):
    description = "This error is raised when the schema is claimed to be complete but missing some components"
    fix = "Either provide the missing components or change the schema to partial"
    missing_component: dm.ContainerId | dm.ViewId

    def message(self) -> str:
        return (
            "The data model schema is set to be complete, however, "
            f"the referred component {self.missing_component} is not preset."
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["missing_component"] = self.missing_component
        return output


@dataclass(frozen=True)
class DuplicatedViewInDataModelError(DMSSchemaError):
    description = "The view is duplicated in the DataModel"
    fix = "Remove the duplicated view"
    error_name: ClassVar[str] = "DuplicatedViewInDataModel"
    referred_by: dm.DataModelId
    view: dm.ViewId

    def message(self) -> str:
        return f"The view {self.view} is duplicated in the DataModel {self.referred_by}"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["referred_by"] = self.referred_by
        output["view"] = self.view
        return output


@dataclass(frozen=True)
class DirectRelationMissingSourceWarning(DMSSchemaWarning):
    description = "The source view referred to by the DirectRelation does not exist"
    fix = "Create the source view"
    error_name: ClassVar[str] = "DirectRelationMissingSource"
    view_id: dm.ViewId
    property: str

    def message(self) -> str:
        return f"The source view referred to by '{self.view_id.external_id}.{self.property}' does not exist."

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = self.view_id
        output["property"] = self.property
        return output


@dataclass(frozen=True)
class MissingViewInModelWarning(DMSSchemaWarning):
    description = "The data model contains view pointing to views not present in the data model"
    fix = "Add the view(s) to the data model"
    error_name: ClassVar[str] = "MissingViewInModel"
    data_model_id: dm.DataModelId
    view_ids: set[dm.ViewId]

    def message(self) -> str:
        return f"The view(s) {self.view_ids} are missing in the data model {self.data_model_id}"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["data_model_id"] = self.data_model_id.dump()
        output["view_id"] = [view_id.dump() for view_id in self.view_ids]
        return output


@dataclass(frozen=True)
class ContainerPropertyUsedMultipleTimesError(DMSSchemaError):
    description = "The container property is used multiple times by the same view property"
    fix = "Use unique container properties for when mapping to the same container"
    error_name: ClassVar[str] = "ContainerPropertyUsedMultipleTimes"
    container: dm.ContainerId
    property: str
    referred_by: frozenset[tuple[dm.ViewId, str]]

    def message(self) -> str:
        return (
            f"The container property {self.property} of {self.container} is used multiple times "
            f"by the same view {self.referred_by}"
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["container"] = self.container
        output["property"] = self.property
        output["referred_by"] = sorted(self.referred_by)
        return output


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
