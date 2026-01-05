import itertools
import sys
from abc import ABC, abstractmethod
from collections import UserList, defaultdict
from collections.abc import Hashable, Sequence
from enum import Enum
from typing import Any, Generic, Literal, TypeAlias, cast

from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms import (
    BaseModelObject,
    Constraint,
    ContainerConstraintReference,
    ContainerIndexReference,
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelRequest,
    DataModelResource,
    Index,
    T_DataModelResource,
    T_ResourceId,
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

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the change."""
        ...


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
    message: str | None = None

    @property
    def change_type(self) -> Literal["create", "update", "delete", "unchanged", "skip"]:
        if self.current_value is None and self.new_value is not None:
            return "create"
        elif self.new_value is None and self.current_value is not None:
            return "delete"
        elif self.changes:
            return "update"
        elif self.new_value is None and self.current_value is None:
            return "skip"
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

    @property
    def skip(self) -> list[ResourceChange[T_ResourceId, T_DataModelResource]]:
        return [change for change in self.resources if change.change_type == "skip"]


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


class ResourceDeploymentPlanList(UserList[ResourceDeploymentPlan]):
    def consolidate_changes(self) -> Self:
        """Consolidate the deployment plans by applying field removals to the new_value of resources."""
        return type(self)([self._consolidate_resource_plan(plan) for plan in self.data])

    def _consolidate_resource_plan(self, plan: ResourceDeploymentPlan) -> ResourceDeploymentPlan:
        consolidated_resources = [
            self._consolidate_resource_change(resource_change) for resource_change in plan.resources
        ]
        return plan.model_copy(update={"resources": consolidated_resources})

    def _consolidate_resource_change(
        self, resource: ResourceChange[T_ResourceId, T_DataModelResource]
    ) -> ResourceChange[T_ResourceId, T_DataModelResource]:
        if resource.new_value is None and resource.current_value is not None:
            # Changed deletion (new_value is None and curren_value is not None) to unchanged by copying
            # current_value to new_value.
            updated_resource = resource.model_copy(update={"new_value": resource.current_value})
        elif resource.changes and resource.new_value is not None:
            # Find all field removals and update new_value accordingly.
            removals = [change for change in resource.changes if isinstance(change, RemovedField)]
            addition_paths = {change.field_path for change in resource.changes if isinstance(change, AddedField)}
            if removals:
                if resource.current_value is None:
                    raise RuntimeError("Bug in Neat: current_value is None for a resource with removals.")
                new_value = self._consolidate_resource(
                    resource.current_value, resource.new_value, removals, addition_paths
                )

                updated_resource = resource.model_copy(
                    update={
                        "new_value": new_value,
                        "changes": [
                            change
                            for change in resource.changes
                            if not isinstance(change, RemovedField)
                            or (isinstance(change, RemovedField) and change.field_path in addition_paths)
                        ],
                    }
                )
            else:
                # No removals, keep as is.
                updated_resource = resource
        else:
            # Creation or unchanged, keep as is.
            updated_resource = resource
        return updated_resource

    def _consolidate_resource(
        self, current: DataModelResource, new: DataModelResource, removals: list[RemovedField], addition_paths: set[str]
    ) -> DataModelResource:
        if isinstance(new, DataModelRequest):
            if not isinstance(current, DataModelRequest):
                # This should not happen, as only containers, views, and data models have removable fields.
                raise RuntimeError("Bug in Neat: current value is not a DataModelRequest during consolidation.")
            return self._consolidate_data_model(current, new)
        elif isinstance(new, ViewRequest):
            return self._consolidate_view(new, removals)
        elif isinstance(new, ContainerRequest):
            return self._consolidate_container(new, removals, addition_paths)
        elif removals:
            # This should not happen, as only containers, views, and data models have removable fields.
            raise RuntimeError("Bug in Neat: attempted to consolidate removals for unsupported resource type.")
        return new

    @staticmethod
    def _consolidate_data_model(current: DataModelRequest, new: DataModelRequest) -> DataModelResource:
        current_views = set(v for v in (current.views or []))
        new_only_views = [v for v in (new.views or []) if v not in current_views]
        final_views = (current.views or []) + new_only_views
        return new.model_copy(update={"views": final_views}, deep=True)

    @staticmethod
    def _consolidate_view(resource: ViewRequest, removals: list[RemovedField]) -> DataModelResource:
        view_properties = resource.properties.copy()
        for removal in removals:
            if removal.field_path.startswith("properties."):
                prop_key = removal.field_path.removeprefix("properties.")
                view_properties[prop_key] = cast(ViewRequestProperty, removal.current_value)
        return resource.model_copy(update={"properties": view_properties}, deep=True)

    @staticmethod
    def _consolidate_container(
        resource: ContainerRequest, removals: list[RemovedField], addition_paths: set[str]
    ) -> DataModelResource:
        container_properties = resource.properties.copy()
        indexes = (resource.indexes or {}).copy()
        constraints = (resource.constraints or {}).copy()
        for removal in removals:
            if removal.field_path.startswith("properties."):
                prop_key = removal.field_path.removeprefix("properties.")
                container_properties[prop_key] = cast(ContainerPropertyDefinition, removal.current_value)
            elif removal.field_path.startswith("indexes.") and removal.field_path not in addition_paths:
                # Index was removed and not re-added, so we need to restore it.
                index_key = removal.field_path.removeprefix("indexes.")
                indexes[index_key] = cast(Index, removal.current_value)
            elif removal.field_path.startswith("constraints.") and removal.field_path not in addition_paths:
                # Constraint was removed and not re-added, so we need to restore it.
                constraint_key = removal.field_path.removeprefix("constraints.")
                constraints[constraint_key] = cast(Constraint, removal.current_value)
        return resource.model_copy(
            update={"properties": container_properties, "indexes": indexes or None, "constraints": constraints or None},
            deep=True,
        )

    def force_changes(self, drop_data: bool) -> Self:
        """Force all resources by deleting and recreating them.

        Args:
            drop_data: If True, containers will be deleted and recreated. If False, containers
                will be consolidated instead.
        Returns:
            A new ResourceDeploymentPlanList with forced changes.
        """
        forced_plans: list[ResourceDeploymentPlan] = []
        for plan in self.data:
            forced_resources: list[ResourceChange] = []
            for resource in plan.resources:
                if resource.change_type == "update" and resource.severity == SeverityType.BREAKING:
                    if drop_data or plan.endpoint != "containers":
                        deletion = resource.model_copy(deep=True, update={"new_value": None, "changes": []})
                        recreation = resource.model_copy(deep=True, update={"current_value": None, "changes": []})
                        forced_resources.append(deletion)
                        forced_resources.append(recreation)
                    else:
                        # For containers, we try to consolidate instead of deleting and recreating.
                        # Note that there might still be breaking changes left which will cause the deployment to fail.
                        # For example, if the usedFor field has changed from node->edge, then this cannot be
                        # consolidated.
                        consolidated_resource = self._consolidate_resource_change(resource)
                        forced_resources.append(consolidated_resource)
                else:
                    # No need to force, keep as is.
                    forced_resources.append(resource)
            forced_plans.append(plan.model_copy(update={"resources": forced_resources}))
        return type(self)(forced_plans)


class ChangeResult(BaseDeployObject, Generic[T_ResourceId, T_DataModelResource], ABC):
    endpoint: DataModelEndpoint
    change: ResourceChange[T_ResourceId, T_DataModelResource]

    @property
    @abstractmethod
    def message(self) -> str:
        """Human-readable message about the change result."""
        ...

    @property
    @abstractmethod
    def is_success(self) -> bool:
        """Whether the change was successful."""
        ...


class HTTPChangeResult(ChangeResult[T_ResourceId, T_DataModelResource]):
    http_message: (
        SuccessResponseItems[T_ResourceId] | FailedResponseItems[T_ResourceId] | FailedRequestItems[T_ResourceId]
    )

    @property
    def message(self) -> str:
        if isinstance(self.http_message, SuccessResponse):
            return "Success"
        elif isinstance(self.http_message, FailedResponseItems):
            error = self.http_message.error
            return f"Failed: {error.code} | {error.message}"
        elif isinstance(self.http_message, FailedRequestItems):
            return f"Request Failed: {self.http_message.message}"
        else:
            return "Unknown result"

    @property
    def is_success(self) -> bool:
        return isinstance(self.http_message, SuccessResponse)


class MultiHTTPChangeResult(ChangeResult[T_ResourceId, T_DataModelResource]):
    http_messages: list[
        SuccessResponseItems[T_ResourceId] | FailedResponseItems[T_ResourceId] | FailedRequestItems[T_ResourceId]
    ]

    @property
    def message(self) -> str:
        error_messages: list[str] = []
        for msg in self.http_messages:
            if isinstance(msg, SuccessResponse):
                continue
            elif isinstance(msg, FailedResponseItems):
                error = msg.error
                error_messages.append(f"Failed: {error.code} | {error.message}")
            elif isinstance(msg, FailedRequestItems):
                error_messages.append(f"Request Failed: {msg.message}")
        if not error_messages:
            return "Success"
        return "; ".join(error_messages)

    @property
    def is_success(self) -> bool:
        return all(isinstance(msg, SuccessResponse) for msg in self.http_messages)


class NoOpChangeResult(ChangeResult[T_ResourceId, T_DataModelResource]):
    """A change result representing a no-op, e.g., when a change was skipped or unchanged."""

    reason: str

    @property
    def message(self) -> str:
        return self.reason

    @property
    def is_success(self) -> bool:
        return True


class ChangedFieldResult(BaseDeployObject, Generic[T_ResourceId, T_Reference]):
    resource_id: T_ResourceId
    field_change: FieldChange
    http_message: SuccessResponseItems[T_Reference] | FailedResponseItems[T_Reference] | FailedRequestItems[T_Reference]


class AppliedChanges(BaseDeployObject):
    """The result of applying changes to the data model.

    Contains lists of created, updated, deleted, and unchanged resources.

    In addition, it has changed fields which tracks the removal of indexes and constraints from containers.
    This is needed as these changes are done with a separate API call per change.
    """

    created: list[HTTPChangeResult] = Field(default_factory=list)
    updated: list[HTTPChangeResult] = Field(default_factory=list)
    deletions: list[HTTPChangeResult] = Field(default_factory=list)
    unchanged: list[NoOpChangeResult] = Field(default_factory=list)
    skipped: list[NoOpChangeResult] = Field(default_factory=list)
    changed_fields: list[ChangedFieldResult] = Field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return all(
            # MyPy fails to understand that ChangeFieldResult.message has the same structure as ChangeResult.message
            isinstance(change.http_message, SuccessResponse)  # type: ignore[attr-defined]
            for change in itertools.chain(self.created, self.updated, self.deletions, self.changed_fields)
        )

    @property
    def merged_updated(self) -> Sequence[ChangeResult]:
        """Merges the changed field into the updated changes."""
        if not self.changed_fields:
            return self.updated
        changed_fields_by_id: dict[Hashable, list[ChangedFieldResult]] = defaultdict(list)
        for changed_field in self.changed_fields:
            changed_fields_by_id[changed_field.resource_id].append(changed_field)
        merged_changes: list[ChangeResult] = []
        for update in self.updated:
            if update.change.resource_id not in changed_fields_by_id:
                merged_changes.append(update)
                continue

            field_changes = changed_fields_by_id[update.change.resource_id]
            merged_change = update.change.model_copy(
                update={"changes": update.change.changes + [fc.field_change for fc in field_changes]}
            )

            # MyPy wants an annotation were we want this to be generic.
            merged_result = MultiHTTPChangeResult(  # type: ignore[var-annotated]
                endpoint=update.endpoint,
                change=merged_change,
                http_messages=[update.http_message] + [fc.http_message for fc in field_changes],
            )
            merged_changes.append(merged_result)

        return merged_changes

    def as_recovery_plan(self) -> list[ResourceDeploymentPlan]:
        """Generate a recovery plan based on the applied changes."""
        recovery_plan: dict[DataModelEndpoint, ResourceDeploymentPlan] = {}
        for change_result in itertools.chain(self.created, self.updated, self.deletions):
            if not isinstance(change_result.http_message, SuccessResponse):
                continue  # Skip failed changes.
            change = change_result.change
            if change.change_type == "create":
                # To recover a created resource, we need to delete it.
                # MyPy wants an annotation were we want this to be generic.
                recovery_change = ResourceChange(  # type: ignore[var-annotated]
                    resource_id=change.resource_id,
                    current_value=change.new_value,
                    new_value=None,
                    changes=[],
                )
            elif change.change_type == "delete":
                # To recover a deleted resource, we need to create it.
                recovery_change = ResourceChange(
                    resource_id=change.resource_id,
                    current_value=None,
                    new_value=change.current_value,
                    changes=[],
                )
            elif change.change_type == "update":
                # To recover an updated resource, we need to revert to the previous state.
                recovery_change = ResourceChange(
                    resource_id=change.resource_id,
                    current_value=change.new_value,
                    new_value=change.current_value,
                    changes=self._reverse_changes(change.changes),
                )
            else:
                continue  # Unchanged resources do not need recovery.

            if change_result.endpoint not in recovery_plan:
                recovery_plan[change_result.endpoint] = ResourceDeploymentPlan(
                    endpoint=change_result.endpoint, resources=[]
                )
            recovery_plan[change_result.endpoint].resources.append(recovery_change)

        return list(recovery_plan.values())

    def _reverse_changes(self, changes: list[FieldChange]) -> list[FieldChange]:
        reversed_changes: list[FieldChange] = []
        for change in changes:
            if isinstance(change, AddedField):
                reversed_changes.append(
                    RemovedField(
                        field_path=change.field_path,
                        current_value=change.new_value,
                        item_severity=change.item_severity,
                    )
                )
            elif isinstance(change, RemovedField):
                reversed_changes.append(
                    AddedField(
                        field_path=change.field_path,
                        new_value=change.current_value,
                        item_severity=change.item_severity,
                    )
                )
            elif isinstance(change, ChangedField):
                reversed_changes.append(
                    ChangedField(
                        field_path=change.field_path,
                        current_value=change.new_value,
                        new_value=change.current_value,
                        item_severity=change.item_severity,
                    )
                )
            elif isinstance(change, FieldChanges):
                reversed_changes.append(
                    FieldChanges(
                        field_path=change.field_path,
                        changes=self._reverse_changes(change.changes),
                    )
                )
        return reversed_changes


class DeploymentResult(BaseDeployObject):
    status: Literal["success", "failure", "partial", "pending", "recovered", "recovery_failed"]
    plan: list[ResourceDeploymentPlan]
    snapshot: SchemaSnapshot
    responses: AppliedChanges | None = None
    recovery: AppliedChanges | None = None

    @property
    def is_dry_run(self) -> bool:
        return self.responses is None

    @property
    def is_success(self) -> bool:
        return self.status in ("success", "pending")

    def as_mixpanel_event(self) -> dict[str, Any]:
        """Convert deployment result to mixpanel event format"""
        output: dict[str, Any] = {
            "status": self.status,
            "isDryRun": self.is_dry_run,
            "isSuccess": self.is_success,
        }
        if self.responses:
            counts: dict[str, int] = defaultdict(int)
            for change in itertools.chain(self.responses.created, self.responses.updated, self.responses.deletions):
                suffix = type(change.http_message).__name__.removesuffix("[TypeVar]").removesuffix("[~T_ResourceId]")
                # For example: containers.created.successResponseItems
                prefix = f"{change.endpoint}.{change.change.change_type}.{suffix}"
                counts[prefix] += len(change.http_message.ids)

            output.update(counts)
        return output


def humanize_changes(changes: Sequence[FieldChange]) -> str:
    primitive_changes = get_primitive_changes(changes)
    lines = []
    for change in primitive_changes:
        lines.append(f"- Field '{change.field_path}': {change.description}")
    return "\n".join(lines)


def get_primitive_changes(changes: Sequence[FieldChange]) -> list[PrimitiveField]:
    primitive_changes: list[PrimitiveField] = []
    for change in changes:
        if isinstance(change, FieldChanges):
            primitive_changes.extend(get_primitive_changes(change.changes))
        elif isinstance(change, PrimitiveField):
            primitive_changes.append(change)
        else:
            raise NotImplementedError(f"Unknown FieldChange type: {type(change)}")
    return primitive_changes
