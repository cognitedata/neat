from abc import ABC
from dataclasses import dataclass
from typing import Any, ClassVar

from cognite.client.data_classes import data_modeling as dm

from .base import NeatValidationError, ValidationWarning

__all__ = [
    "DMSSchemaError",
    "DMSSchemaWarning",
    "MissingSpaceError",
    "MissingContainerError",
    "MissingContainerPropertyError",
    "MissingViewError",
    "MissingParentViewError",
    "MissingSourceViewError",
    "MissingEdgeViewError",
    "DirectRelationMissingSourceWarning",
    "ViewModelVersionNotMatchingWarning",
    "DuplicatedViewInDataModelError",
    "ContainerPropertyUsedMultipleTimesError",
    "EmptyContainerWarning",
    "UnsupportedRelationWarning",
    "MultipleReferenceWarning",
    "HasDataFilterOnNoPropertiesViewWarning",
    "ReverseRelationMissingOtherSideWarning",
    "NodeTypeFilterOnParentViewWarning",
    "ChangingContainerError",
    "ChangingViewError",
]


@dataclass(frozen=True)
class DMSSchemaError(NeatValidationError, ABC): ...


@dataclass(frozen=True)
class DMSSchemaWarning(ValidationWarning, ABC): ...


@dataclass(frozen=True)
class MissingSpaceError(DMSSchemaError):
    description = "The spaced referred to by the Container/View/Node/Edge/DataModel does not exist"
    fix = "Create the space"
    space: str
    referred_by: dm.ContainerId | dm.ViewId | dm.NodeId | dm.EdgeId | dm.DataModelId

    def message(self) -> str:
        return f"The space {self.space} referred to by {self.referred_by} does not exist"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["space"] = self.space
        output["referred_by"] = self.referred_by
        return output


@dataclass(frozen=True)
class MissingContainerError(DMSSchemaError):
    description = "The container referred to by the View does not exist"
    fix = "Create the container"
    error_name: ClassVar[str] = "MissingContainer"
    container: dm.ContainerId
    referred_by: dm.ViewId | dm.ContainerId

    def message(self) -> str:
        return f"The container {self.container} referred to by {self.referred_by} does not exist"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["container"] = self.container
        output["referred_by"] = self.referred_by
        return output


@dataclass(frozen=True)
class MissingContainerPropertyError(DMSSchemaError):
    description = "The property referred to by the View does not exist in the container"
    fix = "Create the property"
    error_name: ClassVar[str] = "MissingContainerProperty"
    container: dm.ContainerId
    property: str
    referred_by: dm.ViewId

    def message(self) -> str:
        return (
            f"The property {self.property} referred to by the container {self.container} "
            f"does not exist in {self.referred_by}"
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["container"] = self.container
        output["property"] = self.property
        output["referred_by"] = self.referred_by
        return output


@dataclass(frozen=True)
class MissingViewError(DMSSchemaError):
    description = "The view referred to by the View/DataModel does not exist"
    fix = "Create the view"
    error_name: ClassVar[str] = "MissingView"
    view: dm.ViewId
    referred_by: dm.DataModelId | dm.ViewId

    def message(self) -> str:
        return f"The view {self.view} referred to by {self.referred_by} does not exist"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view"] = self.view
        output["referred_by"] = self.referred_by
        return output


@dataclass(frozen=True)
class MissingParentViewError(MissingViewError):
    description = "The parent view referred to by the View does not exist"
    fix = "Create the parent view"
    error_name: ClassVar[str] = "MissingParentView"
    referred_by: dm.ViewId

    def message(self) -> str:
        return f"The parent view {self.view} referred to by {self.referred_by} does not exist"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["referred_by"] = self.referred_by
        return output


@dataclass(frozen=True)
class MissingSourceViewError(MissingViewError):
    description = "The source view referred to by the View does not exist"
    fix = "Create the source view"
    error_name: ClassVar[str] = "MissingSourceView"
    property: str
    referred_by: dm.ViewId

    def message(self) -> str:
        return f"The source view {self.view} referred to by {self.referred_by}.{self.property} does not exist"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["property"] = self.property
        return output


@dataclass(frozen=True)
class MissingEdgeViewError(MissingViewError):
    description = "The edge view referred to by the View does not exist"
    fix = "Create the edge view"
    error_name: ClassVar[str] = "MissingEdgeView"
    property: str
    referred_by: dm.ViewId

    def message(self) -> str:
        return f"The edge view {self.view} referred to by {self.referred_by}.{self.property} does not exist"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["property"] = self.property
        output["referred_by"] = self.referred_by
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
class ViewModelVersionNotMatchingWarning(DMSSchemaWarning):
    description = "The view model version does not match the data model version"
    fix = "Update the view model version to match the data model version"
    error_name: ClassVar[str] = "ViewModelVersionNotMatching"
    view_ids: list[dm.ViewId]
    data_model_version: str

    def message(self) -> str:
        return (
            f"The version in the views {self.view_ids} does not match the version in the data model "
            f"{self.data_model_version}. This is not recommended as it easily leads to confusion and errors. "
            f"Views are very cheap and we recommend you update the version of the views to match the data"
            f" model version, irrespective of whether the views have changed or not."
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = [view_id.dump() for view_id in self.view_ids]
        output["data_model_version"] = self.data_model_version
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


@dataclass(frozen=True)
class EmptyContainerWarning(DMSSchemaWarning):
    description = "The container is empty"
    fix = "Add data to the container"
    error_name: ClassVar[str] = "EmptyContainerWarning"
    container_id: dm.ContainerId

    def message(self) -> str:
        return (
            f"The container {self.container_id} is empty. Is this intended? Skipping this container "
            "in the data model."
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["container_id"] = self.container_id.dump()
        return output


@dataclass(frozen=True)
class UnsupportedRelationWarning(DMSSchemaWarning):
    description = "The relatio type is not supported by neat"
    fix = "Change the relation to a supported type"
    error_name: ClassVar[str] = "UnsupportedRelationWarning"
    view_id: dm.ViewId
    property: str
    relation: str

    def message(self) -> str:
        return (
            f"The relation {self.relation} in {self.view_id}.{self.property} is not supported."
            "This property will be ignored."
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = self.view_id.dump()
        output["property"] = self.property
        output["relation"] = self.relation
        return output


@dataclass(frozen=True)
class ReverseRelationMissingOtherSideWarning(DMSSchemaWarning):
    description = "The relation is missing the other side"
    fix = "Add the other side of the relation"
    error_name: ClassVar[str] = "ReverseRelationMissingOtherSideWarning"
    view_id: dm.ViewId
    property: str

    def message(self) -> str:
        return f"The reverse relation specified in {self.view_id}.{self.property} is missing the other side."

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = self.view_id.dump()
        output["property"] = self.property
        return output


@dataclass(frozen=True)
class MultipleReferenceWarning(DMSSchemaWarning):
    description = "The view is implements multiple views from other spaces"
    fix = "Neat expects maximum one implementation of a view from another space"
    error_name: ClassVar[str] = "MultipleReferenceWarning"
    view_id: dm.ViewId
    implements: list[dm.ViewId]

    def message(self) -> str:
        return f"The view {self.view_id} implements multiple views from other spaces: {self.implements}. " + self.fix

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = self.view_id.dump()
        output["implements"] = [view.dump() for view in self.implements]
        return output


@dataclass(frozen=True)
class HasDataFilterOnNoPropertiesViewWarning(DMSSchemaWarning):
    description = "Attempting to set a HasData filter on a view without properties."
    fix = "Add properties to the view or use a node type filter"
    error_name: ClassVar[str] = "HasDataFilterOnNoPropertiesViewWarning"
    view_id: dm.ViewId

    def message(self) -> str:
        return (
            f"Cannot set hasData filter on view {self.view_id} as it does not have properties in any containers. "
            "Using a node type filter instead."
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = self.view_id.dump()
        return output


@dataclass(frozen=True)
class NodeTypeFilterOnParentViewWarning(DMSSchemaWarning):
    description = (
        "Setting a node type filter on a parent view. This is not "
        "recommended as parent views are typically used for multiple type of nodes."
    )
    fix = "Use a HasData filter instead"
    error_name: ClassVar[str] = "NodeTypeFilterOnParentViewWarning"
    view_id: dm.ViewId

    def message(self) -> str:
        return (
            f"Setting a node type filter on parent view {self.view_id}. This is not recommended as "
            "parent views are typically used for multiple types of nodes."
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = self.view_id.dump()
        return output


@dataclass(frozen=True)
class HasDataFilterOnViewWithReferencesWarning(DMSSchemaWarning):
    description = (
        "Setting a hasData filter on a solution view which reference other containers is not recommended."
        "This will lead to no nodes being returned when querying the solution view."
    )
    fix = "Use a node type filter instead"
    error_name: ClassVar[str] = "HasDataFilterOnReferencedViewWarning"

    view_id: dm.ViewId
    references: list[dm.ViewId]

    def message(self) -> str:
        return (
            f"Setting a hasData filter on view {self.view_id} which references other views {self.references}. "
            "This is not recommended as it will lead to no nodes being returned when querying the solution view."
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = self.view_id.dump()
        output["references"] = [view.dump() for view in sorted(self.references, key=lambda x: x.as_tuple())]
        return output
