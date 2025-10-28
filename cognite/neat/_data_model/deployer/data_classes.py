from abc import ABC, abstractmethod
from datetime import datetime
from typing import Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from cognite.neat._data_model.models.dms import (
    APIResource,
    ContainerRequest,
    DataModelReference,
    DataModelRequest,
    NodeReference,
    SpaceRequest,
    T_Reference,
    ViewReference,
    ViewRequest,
)
from cognite.neat._data_model.models.dms._base import BaseModelObject, ReferenceObject
from cognite.neat._utils.http_client._data_classes import HTTPMessage

JsonPath: TypeAlias = str  # e.g., 'properties.temperature', 'constraints.uniqueKey'
# Todo Severity Type -> Enum
SeverityType: TypeAlias = Literal["safe", "warning", "breaking"]
DataModelEndpoint: TypeAlias = Literal["spaces", "containers", "views", "datamodels", "instances"]
T_Resource = TypeVar("T_Resource", bound=APIResource)
T_Item = TypeVar("T_Item", bound=BaseModelObject)


class BaseDeployObject(BaseModel, alias_generator=to_camel, extra="ignore", populate_by_name=True):
    """Base class for all deployer data model objects."""

    ...


class PropertyChange(BaseDeployObject, ABC):
    """Represents a change to a specific property or field."""

    field_path: JsonPath

    @abstractmethod
    @property
    def severity(self) -> SeverityType:
        """The severity of the change."""
        raise NotImplementedError()


class AddedProperty(PropertyChange):
    item_severity: SeverityType
    new_value: str | int | float | bool | None

    @property
    def description(self) -> str:
        return f"added with value {self.new_value!r}"

    @property
    def severity(self) -> SeverityType:
        return self.item_severity


class RemovedProperty(PropertyChange):
    item_severity: SeverityType
    old_value: str | int | float | bool | None

    @property
    def description(self) -> str:
        return f"removed (was {self.old_value!r})"

    @property
    def severity(self) -> SeverityType:
        return self.item_severity


class PrimitivePropertyChange(PropertyChange):
    item_severity: SeverityType
    new_value: str | int | float | bool | None
    old_value: str | int | float | bool | None

    @property
    def description(self) -> str:
        return f"changed from {self.old_value!r} to {self.new_value!r}"

    @property
    def severity(self) -> SeverityType:
        return self.item_severity


class ContainerPropertyChange(PropertyChange):
    changed_items: list[PropertyChange]

    @property
    def severity(self) -> SeverityType:
        if any(item.severity == "breaking" for item in self.changed_items):
            return "breaking"
        elif any(item.severity == "warning" for item in self.changed_items):
            return "warning"
        else:
            return "safe"


class ResourceChange(BaseDeployObject, Generic[T_Reference, T_Resource]):
    resource_id: T_Resource
    new_value: T_Resource
    old_value: T_Resource | None = None
    changes: list[PropertyChange] = Field(default_factory=list)

    @property
    def change_type(self) -> Literal["create", "update", "delete", "unchanged"]:
        if self.old_value is None:
            return "create"
        elif self.changes:
            return "update"
        else:
            return "unchanged"

    @property
    def severity(self) -> SeverityType:
        if any(change.severity == "breaking" for change in self.changes):
            return "breaking"
        elif any(change.severity == "warning" for change in self.changes):
            return "warning"
        else:
            return "safe"


class ResourceDeploymentPlan(BaseDeployObject, Generic[T_Reference, T_Resource]):
    endpoint: DataModelEndpoint
    resources: list[ResourceChange[T_Reference, T_Resource]]

    @property
    def to_create(self) -> list[ResourceChange[T_Reference, T_Resource]]:
        return [change for change in self.resources if change.change_type == "create"]

    @property
    def to_update(self) -> list[ResourceChange[T_Reference, T_Resource]]:
        return [change for change in self.resources if change.change_type == "update"]

    @property
    def to_delete(self) -> list[ResourceChange[T_Reference, T_Resource]]:
        return [change for change in self.resources if change.change_type == "delete"]

    @property
    def unchanged(self) -> list[ResourceChange[T_Reference, T_Resource]]:
        return [change for change in self.resources if change.change_type == "unchanged"]


class SchemaSnapshot(BaseDeployObject):
    timestamp: datetime
    data_model: dict[DataModelReference, DataModelRequest]
    views: dict[ViewReference, ViewRequest]
    containers: dict[ReferenceObject, ContainerRequest]
    spaces: dict[str, SpaceRequest]
    node_types: dict[NodeReference, NodeReference]


class ChangeResult(BaseDeployObject, Generic[T_Reference, T_Resource]):
    change: ResourceChange[T_Reference, T_Resource]
    message: HTTPMessage


class AppliedChanges(BaseDeployObject):
    status: Literal["success", "failure", "partial"]
    created: list[ChangeResult] = Field(default_factory=list)
    updated: list[ChangeResult] = Field(default_factory=list)
    deletions: list[ChangeResult] = Field(default_factory=list)

    @property
    def is_success(self) -> bool:
        raise NotImplementedError()

    def as_recovery_plan(self) -> list[ResourceDeploymentPlan]:
        raise NotImplementedError()


class DeploymentResult(BaseDeployObject):
    status: Literal["success", "failure", "partial", "pending"]
    plan: list[ResourceDeploymentPlan]
    snapshot: SchemaSnapshot
    responses: AppliedChanges | None = None
    recovery: AppliedChanges | None = None

    @property
    def is_dry_run(self) -> bool:
        return self.status == "pending"

    @property
    def is_success(self) -> bool:
        return self.status == "success"
