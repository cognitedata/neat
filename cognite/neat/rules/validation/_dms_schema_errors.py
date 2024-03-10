from abc import ABC
from dataclasses import dataclass
from functools import total_ordering
from typing import Any, ClassVar

from cognite.client.data_classes import data_modeling as dm

from ._base import Error


@dataclass(frozen=True)
@total_ordering
class DMSSchemaError(Error, ABC):
    def __lt__(self, other: object) -> bool:
        if not isinstance(other, DMSSchemaError):
            return NotImplemented
        return type(self).__name__ < type(other).__name__

    def __eq__(self, other) -> bool:
        if not isinstance(other, DMSSchemaError):
            return NotImplemented
        return type(self).__name__ == type(other).__name__


@dataclass(frozen=True)
class MissingSpace(DMSSchemaError):
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
class MissingContainer(DMSSchemaError):
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
class MissingContainerProperty(DMSSchemaError):
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
class MissingView(DMSSchemaError):
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
class MissingParentView(MissingView):
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
class MissingSourceView(MissingView):
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
class MissingEdgeView(MissingView):
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
class DuplicatedViewInDataModel(DMSSchemaError):
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
class DirectRelationMissingSource(DMSSchemaError):
    description = "The source view referred to by the DirectRelation does not exist"
    fix = "Create the source view"
    error_name: ClassVar[str] = "DirectRelationMissingSource"
    view_id: dm.ViewId
    property: str

    def message(self) -> str:
        return f"The source view referred to by {self.view_id}.{self.property} does not exist"

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = self.view_id
        output["property"] = self.property
        return output


@dataclass(frozen=True)
class ContainerPropertyUsedMultipleTimes(DMSSchemaError):
    description = "The container property is used multiple times by the same view"
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
