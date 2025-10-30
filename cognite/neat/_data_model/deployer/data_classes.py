from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Generic, Literal, TypeAlias

from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from cognite.neat._data_model.models.dms import (
    BaseModelObject,
    ContainerReference,
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


class FieldChange(BaseDeployObject, ABC):
    """Represents a change to a specific property or field."""

    field_path: JsonPath

    @property
    @abstractmethod
    def severity(self) -> SeverityType:
        """The severity of the change."""
        raise NotImplementedError()


class PrimitiveField(FieldChange, ABC):
    """Base class for changes to primitive properties."""

    item_severity: SeverityType

    @property
    def severity(self) -> SeverityType:
        return self.item_severity


class AddedField(PrimitiveField):
    new_value: BaseModelObject | str | int | float | bool | None

    @property
    def description(self) -> str:
        return f"added with value {self.new_value!r}"


class RemovedField(PrimitiveField):
    old_value: BaseModelObject | str | int | float | bool | None

    @property
    def description(self) -> str:
        return f"removed (was {self.old_value!r})"


class ChangedField(PrimitiveField):
    new_value: BaseModelObject | str | int | float | bool | None
    current_value: BaseModelObject | str | int | float | bool | None

    @property
    def description(self) -> str:
        if self.new_value is None:
            return f"removed (was {self.current_value!r})"
        elif self.current_value is None:
            return f"added with value {self.new_value!r}"
        return f"changed from {self.current_value!r} to {self.new_value!r}"


class FieldChanges(FieldChange):
    """Represents a nested property, i.e., a property that contains other properties."""

    changes: list[FieldChange]

    @property
    def severity(self) -> SeverityType:
        return SeverityType.max_severity([item.severity for item in self.changes], default=SeverityType.SAFE)


class ResourceChange(BaseDeployObject, Generic[T_Reference, T_Resource]):
    resource_id: T_Reference
    new_value: T_Resource
    old_value: T_Resource | None = None
    changes: list[FieldChange] = Field(default_factory=list)

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
    containers: dict[ContainerReference, ContainerRequest]
    spaces: dict[str, SpaceRequest]
    node_types: dict[NodeReference, NodeReference]


class ChangeResult(BaseDeployObject, Generic[T_Reference, T_Resource]):
    change: ResourceChange[T_Reference, T_Resource]
    message: HTTPMessage


class AppliedChanges(BaseDeployObject, Generic[T_Reference, T_Resource]):
    created: list[ChangeResult[T_Reference, T_Resource]] = Field(default_factory=list)
    updated: list[ChangeResult[T_Reference, T_Resource]] = Field(default_factory=list)
    deletions: list[ChangeResult[T_Reference, T_Resource]] = Field(default_factory=list)


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
