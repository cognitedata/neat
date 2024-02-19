from abc import ABC
from dataclasses import dataclass, field
from typing import ClassVar

from cognite.client import data_modeling as dm


@dataclass
class SchemaError(ABC):
    error_name: ClassVar[str]


@dataclass
class DMSSchema:
    space: dm.SpaceApply
    model: dm.DataModelApply
    views: dm.ViewApplyList = field(default_factory=lambda: dm.ViewApplyList([]))
    containers: dm.ContainerApplyList = field(default_factory=lambda: dm.ContainerApplyList([]))
    node_types: dm.NodeApplyList = field(default_factory=lambda: dm.NodeApplyList([]))

    def validate(self) -> list[SchemaError]:
        raise NotImplementedError


@dataclass
class MissingSpace(SchemaError):
    error_name: ClassVar[str] = "NonExistentSpace"
    space: str
    referred_by: set[dm.ContainerId | dm.ViewId | dm.NodeId | dm.EdgeId]


@dataclass
class MissingContainer(SchemaError):
    error_name: ClassVar[str] = "NonExistentContainer"
    container: dm.ContainerId
    referred_by: set[dm.ViewId]


@dataclass
class MissingContainerProperty(SchemaError):
    error_name: ClassVar[str] = "NonExistentContainerProperty"
    container: dm.ContainerId
    property: str
    referred_by: set[dm.ViewId]


@dataclass
class MissingView(SchemaError):
    error_name: ClassVar[str] = "NonExistentView"
    view: dm.ViewId
    referred_by: set[dm.DataModelId]


@dataclass
class DuplicatedViewInDataModel(SchemaError):
    error_name: ClassVar[str] = "DuplicatedViewInDataModel"
    referred_by: set[dm.DataModelId]
    view: dm.ViewId


@dataclass
class DirectRelationMissingSource(SchemaError):
    error_name: ClassVar[str] = "DirectRelationMissingSource"
    view_id: dm.ViewId
    property: str


@dataclass
class ContainerPropertyUsedMultipleTimes(SchemaError):
    error_name: ClassVar[str] = "ContainerPropertyUsedMultipleTimes"
    container: dm.ContainerId
    property: str
    referred_by: set[tuple[dm.ViewId, str]]
