from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Generic, Literal, TypeAlias

from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from cognite.neat._data_model.models.dms import (
    ContainerRequest,
    DataModelReference,
    DataModelRequest,
    NodeReference,
    SpaceRequest,
    T_Reference,
    T_Resource,
    ViewReference,
    ViewRequest,
)
from cognite.neat._data_model.models.dms._base import ReferenceObject
from cognite.neat._utils.http_client._data_classes import HTTPMessage

JsonPath: TypeAlias = str  # e.g., 'properties.temperature', 'constraints.uniqueKey'
DataModelEndpoint: TypeAlias = Literal["spaces", "containers", "views", "datamodels", "instances"]


class SeverityType(Enum):
    SAFE = 1
    WARNING = 2
    BREAKING = 3

    @classmethod
    def max_severity(cls, severities: list["SeverityType"], default: "SeverityType") -> "SeverityType":
        value = max([severity.value for severity in severities], default=default.value)
        return cls(value)


class BaseDeployObject(BaseModel, alias_generator=to_camel, extra="ignore", populate_by_name=True):
    """Base class for all deployer data model objects."""

    ...


class PropertyChange(BaseDeployObject, ABC):
    """Represents a change to a specific property or field."""

    field_path: JsonPath

    @property
    @abstractmethod
    def severity(self) -> SeverityType:
        """The severity of the change."""
        raise NotImplementedError()


class PrimitiveProperty(PropertyChange, ABC):
    """Base class for changes to primitive properties."""

    item_severity: SeverityType

    @property
    def severity(self) -> SeverityType:
        return self.item_severity


class AddedProperty(PrimitiveProperty):
    new_value: str | int | float | bool | None

    @property
    def description(self) -> str:
        return f"added with value {self.new_value!r}"


class RemovedProperty(PrimitiveProperty):
    old_value: str | int | float | bool | None

    @property
    def description(self) -> str:
        return f"removed (was {self.old_value!r})"


class PrimitivePropertyChange(PrimitiveProperty):
    new_value: str | int | float | bool | None
    old_value: str | int | float | bool | None

    @property
    def description(self) -> str:
        return f"changed from {self.old_value!r} to {self.new_value!r}"


class ContainerPropertyChange(PropertyChange):
    """Represents a nested property, i.e., a property that contains other properties."""

    changed_items: list[PropertyChange]

    @property
    def severity(self) -> SeverityType:
        return SeverityType.max_severity([item.severity for item in self.changed_items], default=SeverityType.SAFE)


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
        return SeverityType.max_severity([change.severity for change in self.changes], default=SeverityType.SAFE)


class ResourceDeploymentPlan(BaseDeployObject, Generic[T_Reference, T_Resource]):
    endpoint: DataModelEndpoint
    resources: list[ResourceChange[T_Reference, T_Resource]]

    @property
    def to_upsert(self) -> list[ResourceChange[T_Reference, T_Resource]]:
        return [change for change in self.resources if change.change_type in ("create", "update")]

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
    created: list[ChangeResult] = Field(default_factory=list)
    updated: list[ChangeResult] = Field(default_factory=list)
    deletions: list[ChangeResult] = Field(default_factory=list)


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
