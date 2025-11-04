import itertools
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Generic, Literal, TypeAlias

from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from cognite.neat._data_model.models.dms import (
    BaseModelObject,
    ContainerConstraintReference,
    ContainerIndexReference,
    ContainerReference,
    ContainerRequest,
    DataModelReference,
    DataModelRequest,
    NodeReference,
    SpaceReference,
    SpaceRequest,
    T_DataModelResource,
    T_ResourceId,
    ViewReference,
    ViewRequest,
)
from cognite.neat._utils.http_client import (
    FailedRequestItems,
    FailedResponseItems,
    SuccessResponse,
    SuccessResponseItems,
)
from cognite.neat._utils.useful_types import T_Reference

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
    current_value: BaseModelObject | str | int | float | bool | None

    @property
    def description(self) -> str:
        return f"removed (was {self.current_value!r})"


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


class ResourceChange(BaseDeployObject, Generic[T_ResourceId, T_DataModelResource]):
    resource_id: T_ResourceId
    new_value: T_DataModelResource | None
    current_value: T_DataModelResource | None = None
    changes: list[FieldChange] = Field(default_factory=list)

    @property
    def change_type(self) -> Literal["create", "update", "delete", "unchanged"]:
        if self.current_value is None:
            return "create"
        elif self.new_value is None:
            return "delete"
        elif self.changes:
            return "update"
        else:
            return "unchanged"

    @property
    def severity(self) -> SeverityType:
        return SeverityType.max_severity([change.severity for change in self.changes], default=SeverityType.SAFE)


class ResourceDeploymentPlan(BaseDeployObject, Generic[T_ResourceId, T_DataModelResource]):
    endpoint: DataModelEndpoint
    resources: list[ResourceChange[T_ResourceId, T_DataModelResource]]

    @property
    def to_upsert(self) -> list[ResourceChange[T_ResourceId, T_DataModelResource]]:
        return [change for change in self.resources if change.change_type in ("create", "update")]

    @property
    def to_create(self) -> list[ResourceChange[T_ResourceId, T_DataModelResource]]:
        return [change for change in self.resources if change.change_type == "create"]

    @property
    def to_update(self) -> list[ResourceChange[T_ResourceId, T_DataModelResource]]:
        return [change for change in self.resources if change.change_type == "update"]

    @property
    def to_delete(self) -> list[ResourceChange[T_ResourceId, T_DataModelResource]]:
        return [change for change in self.resources if change.change_type == "delete"]

    @property
    def unchanged(self) -> list[ResourceChange[T_ResourceId, T_DataModelResource]]:
        return [change for change in self.resources if change.change_type == "unchanged"]


class ContainerDeploymentPlan(ResourceDeploymentPlan[ContainerReference, ContainerRequest]):
    endpoint: Literal["containers"] = "containers"
    resources: list[ResourceChange[ContainerReference, ContainerRequest]]

    @property
    def indexes_to_remove(self) -> dict[ContainerIndexReference, RemovedField]:
        indexes: dict[ContainerIndexReference, RemovedField] = {}
        for resource_change in self.resources:
            for change in resource_change.changes:
                if isinstance(change, RemovedField) and change.field_path.startswith("indexes."):
                    # Extract index reference from field path
                    index_identifier = change.field_path.removeprefix("indexes.")
                    indexes[
                        ContainerIndexReference(
                            space=resource_change.resource_id.space,
                            external_id=resource_change.resource_id.external_id,
                            identifier=index_identifier,
                        )
                    ] = change
        return indexes

    @property
    def constraints_to_remove(self) -> dict[ContainerConstraintReference, RemovedField]:
        constraints: dict[ContainerConstraintReference, RemovedField] = {}
        for resource_change in self.resources:
            for change in resource_change.changes:
                if isinstance(change, RemovedField) and change.field_path.startswith("constraints."):
                    # Extract constraint reference from field path
                    constraint_identifier = change.field_path.removeprefix("constraints.")
                    constraints[
                        ContainerConstraintReference(
                            space=resource_change.resource_id.space,
                            external_id=resource_change.resource_id.external_id,
                            identifier=constraint_identifier,
                        )
                    ] = change
        return constraints


class SchemaSnapshot(BaseDeployObject):
    timestamp: datetime
    data_model: dict[DataModelReference, DataModelRequest]
    views: dict[ViewReference, ViewRequest]
    containers: dict[ContainerReference, ContainerRequest]
    spaces: dict[SpaceReference, SpaceRequest]
    node_types: dict[NodeReference, NodeReference]


class ChangeResult(BaseDeployObject, Generic[T_ResourceId, T_DataModelResource]):
    change: ResourceChange[T_ResourceId, T_DataModelResource]
    message: SuccessResponseItems[T_ResourceId] | FailedResponseItems[T_ResourceId] | FailedRequestItems[T_ResourceId]


class ChangedFieldResult(BaseDeployObject, Generic[T_Reference]):
    field_change: FieldChange
    message: SuccessResponseItems[T_Reference] | FailedResponseItems[T_Reference] | FailedRequestItems[T_Reference]


class AppliedChanges(BaseDeployObject):
    """The result of applying changes to the data model.

    Contains lists of created, updated, deleted, and unchanged resources.

    In addition, it has changed fields which tracks the removal of indexes and constraints from containers.
    This is needed as these changes are done with a separate API call per change.
    """

    created: list[ChangeResult] = Field(default_factory=list)
    updated: list[ChangeResult] = Field(default_factory=list)
    deletions: list[ChangeResult] = Field(default_factory=list)
    unchanged: list[ResourceChange] = Field(default_factory=list)
    changed_fields: list[ChangedFieldResult] = Field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return all(
            # MyPy fails to understand that ChangeFieldResult.message has the same structure as ChangeResult.message
            isinstance(change.message, SuccessResponse)  # type: ignore[attr-defined]
            for change in itertools.chain(self.created, self.updated, self.deletions, self.changed_fields)
        )

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
        return self.status in ("success", "pending")
