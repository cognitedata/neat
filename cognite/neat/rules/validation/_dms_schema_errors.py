from abc import ABC
from dataclasses import dataclass
from typing import ClassVar

from cognite.client.data_classes import data_modeling as dm

from ._base import Error


@dataclass(frozen=True, order=True)
class DMSSchemaError(Error, ABC):
    ...


@dataclass(frozen=True, order=True)
class MissingSpace(DMSSchemaError):
    description = "The spaced referred to by the Container/View/Node/Edge/DataModel does not exist"
    fix = "Create the space"
    space: str
    referred_by: dm.ContainerId | dm.ViewId | dm.NodeId | dm.EdgeId | dm.DataModelId

    def message(self) -> str:
        return f"The space {self.space} referred to by {self.referred_by} does not exist"


@dataclass(frozen=True, order=True)
class MissingContainer(DMSSchemaError):
    error_name: ClassVar[str] = "MissingContainer"
    container: dm.ContainerId
    referred_by: dm.ViewId


@dataclass(frozen=True, order=True)
class MissingContainerProperty(DMSSchemaError):
    error_name: ClassVar[str] = "MissingContainerProperty"
    container: dm.ContainerId
    property: str
    referred_by: dm.ViewId


@dataclass(frozen=True, order=True)
class MissingView(DMSSchemaError):
    error_name: ClassVar[str] = "MissingView"
    view: dm.ViewId
    referred_by: dm.DataModelId | dm.ViewId


@dataclass(frozen=True, order=True)
class MissingParentView(MissingView):
    error_name: ClassVar[str] = "MissingParentView"
    referred_by: dm.ViewId


@dataclass(frozen=True, order=True)
class MissingSourceView(MissingView):
    error_name: ClassVar[str] = "MissingSourceView"
    property: str
    referred_by: dm.ViewId


@dataclass(frozen=True, order=True)
class MissingEdgeView(MissingView):
    error_name: ClassVar[str] = "MissingEdgeView"
    property: str
    referred_by: dm.ViewId


@dataclass(frozen=True, order=True)
class DuplicatedViewInDataModel(DMSSchemaError):
    error_name: ClassVar[str] = "DuplicatedViewInDataModel"
    referred_by: dm.DataModelId
    view: dm.ViewId


@dataclass(frozen=True, order=True)
class DirectRelationMissingSource(DMSSchemaError):
    error_name: ClassVar[str] = "DirectRelationMissingSource"
    view_id: dm.ViewId
    property: str


@dataclass(frozen=True, order=True)
class ContainerPropertyUsedMultipleTimes(DMSSchemaError):
    error_name: ClassVar[str] = "ContainerPropertyUsedMultipleTimes"
    container: dm.ContainerId
    property: str
    referred_by: frozenset[tuple[dm.ViewId, str]]
