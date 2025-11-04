import itertools
import sys
from abc import ABC, abstractmethod
from collections import UserList
from datetime import datetime
from enum import Enum
from typing import Generic, Literal, TypeAlias, cast

from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from cognite.neat._data_model.models.dms import (
    BaseModelObject,
    Constraint,
    ContainerConstraintReference,
    ContainerIndexReference,
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelReference,
    DataModelRequest,
    DataModelResource,
    Index,
    NodeReference,
    SpaceReference,
    SpaceRequest,
    T_DataModelResource,
    T_ResourceId,
    ViewReference,
    ViewRequest,
    ViewRequestProperty,
)
from cognite.neat._utils.http_client import (
    FailedRequestItems,
    FailedResponseItems,
    SuccessResponse,
    SuccessResponseItems,
)
from cognite.neat._utils.useful_types import T_Reference

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

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
        return self._get_fields_to_remove("indexes.", ContainerIndexReference)

    @property
    def constraints_to_remove(self) -> dict[ContainerConstraintReference, RemovedField]:
        return self._get_fields_to_remove("constraints.", ContainerConstraintReference)

    def _get_fields_to_remove(self, field_prefix: str, ref_cls: type) -> dict:
        items: dict = {}
        for resource_change in self.resources:
            for change in resource_change.changes:
                if isinstance(change, RemovedField) and change.field_path.startswith(field_prefix):
                    identifier = change.field_path.removeprefix(field_prefix)
                    items[
                        ref_cls(
                            space=resource_change.resource_id.space,
                            external_id=resource_change.resource_id.external_id,
                            identifier=identifier,
                        )
                    ] = change
        return items

    @property
    def to_upsert(self) -> list[ResourceChange[ContainerReference, ContainerRequest]]:
        return [change for change in self.resources if change.change_type == "create" or self._is_update(change)]

    @property
    def to_update(self) -> list[ResourceChange[ContainerReference, ContainerRequest]]:
        return [change for change in self.resources if self._is_update(change)]

    @classmethod
    def _is_update(cls, change: ResourceChange[ContainerReference, ContainerRequest]) -> bool:
        """Whether the container change is an update.

        Containers with only index or constraint removals are not considered updates, as these are handled by a
        separate API call.
        """
        if change.change_type != "update":
            return False
        for c in change.changes:
            if not (
                isinstance(c, RemovedField)
                and (c.field_path.startswith("indexes.") or c.field_path.startswith("constraints."))
            ):
                return True
        return False


class SchemaSnapshot(BaseDeployObject):
    timestamp: datetime
    data_model: dict[DataModelReference, DataModelRequest]
    views: dict[ViewReference, ViewRequest]
    containers: dict[ContainerReference, ContainerRequest]
    spaces: dict[SpaceReference, SpaceRequest]
    node_types: dict[NodeReference, NodeReference]


class ResourceDeploymentPlanList(UserList):
    def consolidate_changes(self) -> Self:
        """Consolidate the deployment plans by applying field removals to the new_value of resources."""
        consolidated_plan: list[ResourceDeploymentPlan] = []
        for plan in self.data:
            consolidated_resources: list[ResourceChange] = []
            for resource in plan.resources:
                if resource.new_value is None and resource.current_value is not None:
                    # Deletion, keep current_value.
                    updated_resource = resource.model_copy(update={"new_value": resource.current_value})
                elif resource.changes and resource.new_value is not None:
                    # Find all field removals and update new_value accordingly.
                    removals = [change for change in resource.changes if isinstance(change, RemovedField)]
                    if removals:
                        new_value = self._consolidate_resource(resource.new_value, removals)
                        updated_resource = resource.model_copy(
                            update={
                                "new_value": new_value,
                                "changes": [
                                    change for change in resource.changes if not isinstance(change, RemovedField)
                                ],
                            }
                        )
                    else:
                        # No removals, keep as is.
                        updated_resource = resource
                else:
                    # Creation or unchanged, keep as is.
                    updated_resource = resource
                consolidated_resources.append(updated_resource)
            consolidated_plan.append(plan.model_copy(update={"resources": consolidated_resources}))
        return type(self)(consolidated_plan)

    def _consolidate_resource(self, resource: DataModelResource, removals: list[RemovedField]) -> DataModelResource:
        if isinstance(resource, DataModelRequest):
            raise NotImplementedError()
        elif isinstance(resource, ViewRequest):
            return self._consolidate_view(resource, removals)
        elif isinstance(resource, ContainerRequest):
            return self._consolidate_container(resource, removals)
        elif removals:
            # This should not happen, as only containers, views, and data models have removable fields.
            raise RuntimeError("Bug in Neat: attempted to consolidate removals for unsupported resource type.")
        return resource

    @staticmethod
    def _consolidate_view(resource: ViewRequest, removals: list[RemovedField]) -> DataModelResource:
        view_properties = resource.properties.copy()
        for removal in removals:
            if removal.field_path.startswith("properties."):
                prop_key = removal.field_path.removeprefix("properties.")
                view_properties[prop_key] = cast(ViewRequestProperty, removal.current_value)
        return resource.model_copy(update={"properties": view_properties}, deep=True)

    @staticmethod
    def _consolidate_container(resource: ContainerRequest, removals: list[RemovedField]) -> DataModelResource:
        container_properties = resource.properties.copy()
        indexes = (resource.indexes or {}).copy()
        constraints = (resource.constraints or {}).copy()
        for removal in removals:
            if removal.field_path.startswith("properties."):
                prop_key = removal.field_path.removeprefix("properties.")
                container_properties[prop_key] = cast(ContainerPropertyDefinition, removal.current_value)
            elif removal.field_path.startswith("indexes."):
                index_key = removal.field_path.removeprefix("indexes.")
                indexes[index_key] = cast(Index, removal.current_value)
            elif removal.field_path.startswith("constraints."):
                constraint_key = removal.field_path.removeprefix("constraints.")
                constraints[constraint_key] = cast(Constraint, removal.current_value)
        return resource.model_copy(
            update={"properties": container_properties, "indexes": indexes or None, "constraints": constraints or None},
            deep=True,
        )


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
