from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel

from cognite.neat._client import NeatClient
from cognite.neat._issues import ConsistencyError, ImplementationWarning, IssueList, ModelSyntaxError

from ._container import ContainerRequest
from ._data_model import DataModelRequest
from ._references import DataModelReference, NodeReference, ReferenceObject, ViewReference
from ._schema import RequestSchema
from ._space import SpaceRequest
from ._views import ViewRequest

T_Item = TypeVar("T_Item", bound=BaseModel)

DataModelingResource: TypeAlias = Literal["space", "container", "view", "data_model", "node"]
Action: TypeAlias = Literal["create", "update", "recreate", "delete", "unchanged"]
ChangeType: TypeAlias = Literal["added", "removed", "modified", "unchanged"]
JsonPath: TypeAlias = str  # e.g., 'properties.temperature', 'constraints.uniqueKey'
SeverityType: TypeAlias = Literal["safe", "warning", "breaking"]


@dataclass
class PropertyChange:
    """Represents a change to a specific property or field."""

    field_path: JsonPath
    change_type: ChangeType
    severity: SeverityType
    description: str


@dataclass
class ResourceDiff(Generic[T_Item]):
    """a change to a single resource."""

    resource_type: DataModelingResource
    resource_id: ReferenceObject | str  # str for spaces, ReferenceObject for others
    action: Action
    changes: list[PropertyChange]
    new_value: T_Item
    old_value: T_Item | None


@dataclass
class ResourceDeploymentPlan(Generic[T_Item]):
    """Categorized changes for all resources."""

    to_create: list[ResourceDiff[T_Item]]
    to_update: list[ResourceDiff[T_Item]]
    to_recreate: list[ResourceDiff[T_Item]]
    unchanged: list[ResourceDiff[T_Item]]


@dataclass
class DeploymentPlan:
    """Overall deployment plan for all resource types."""

    spaces: ResourceDeploymentPlan[SpaceRequest]
    containers: ResourceDeploymentPlan[ContainerRequest]
    views: ResourceDeploymentPlan[ViewRequest]
    data_models: ResourceDeploymentPlan[DataModelRequest]
    nodes: ResourceDeploymentPlan[NodeReference]

    def has_changes(self) -> bool:
        """Check if there are any changes in the deployment plan."""
        plans: list[ResourceDeploymentPlan[Any]] = [
            self.spaces,
            self.containers,
            self.views,
            self.data_models,
            self.nodes,
        ]
        return any(plan.to_create or plan.to_update or plan.to_recreate for plan in plans)


@dataclass
class DeploymentSnapshot:
    """Stores the cdf state before deployment for rollback."""

    timestamp: str
    data_model: dict[DataModelReference, DataModelRequest]
    views: dict[ViewReference, ViewRequest]
    containers: dict[ReferenceObject, ContainerRequest]
    spaces: dict[str, SpaceRequest]
    node_types: dict[NodeReference, NodeReference]


@dataclass
class DeploymentResult:
    """Result of a deployment operation."""

    success: bool
    plan: DeploymentPlan
    applied_changes: list[ResourceDiff]
    failed_changes: list[ResourceDiff]
    snapshot: DeploymentSnapshot | None
    issues: IssueList
    dry_run: bool


@dataclass
class DeploymentOptions:
    """Configuration options for deployment."""

    dry_run: bool = True
    auto_rollback: bool = True
    ignore_warnings: bool = False
    max_severity: SeverityType = "safe"


class SchemaDeployer:
    def __init__(self, data_model: RequestSchema, client: NeatClient, options: DeploymentOptions | None = None) -> None:
        self.data_model: RequestSchema = data_model
        self.client: NeatClient = client
        self.options: DeploymentOptions = options or DeploymentOptions()
        self.issues: IssueList = IssueList()
        self._snapshot: DeploymentSnapshot | None = None

    def deploy(self) -> DeploymentResult:
        """Execute the deployment with dry-run and rollback support."""
        # Step 1: Fetch current cdf state
        self._snapshot = self._fetch_cdf_state()

        # Step 2: Create deployment plan by comparing local vs cdf
        plan = self._create_deployment_plan()

        # Step 3: Analyze changes and collect issues
        self._analyze_changes(plan)

        # Step 4: Check if deployment should proceed
        if not self._should_proceed(plan):
            return DeploymentResult(
                success=False,
                plan=plan,
                applied_changes=[],
                failed_changes=[],
                snapshot=None,
                issues=self.issues,
                dry_run=self.options.dry_run,
            )

        # Step 5: If dry-run, return plan without applying
        if self.options.dry_run:
            return DeploymentResult(
                success=True,
                plan=plan,
                applied_changes=[],
                failed_changes=[],
                snapshot=None,
                issues=self.issues,
                dry_run=True,
            )

        # Step 6: Apply changes
        result = self._apply_changes(plan)

        # Step 7: Rollback if failed and auto_rollback is enabled
        if not result.success and self.options.auto_rollback and self._snapshot:
            self._rollback(self._snapshot)

        return result

    def _fetch_cdf_state(self) -> DeploymentSnapshot:
        """Fetch current state from CDF."""
        # Fetch spaces
        space_ids = [space.space for space in self.data_model.spaces]
        cdf_spaces = self.client.spaces.retrieve(space_ids)

        # Fetch containers
        container_refs = [c.as_reference() for c in self.data_model.containers]
        cdf_containers = self.client.containers.retrieve(container_refs)

        # Fetch views
        view_refs = [v.as_reference() for v in self.data_model.views]
        cdf_views = self.client.views.retrieve(view_refs)

        # Fetch data models
        dm_ref = self.data_model.data_model.as_reference()
        cdf_data_models = self.client.data_models.retrieve([dm_ref])

        nodes = [node_type for view in cdf_views for node_type in view.node_types]

        return DeploymentSnapshot(
            timestamp=datetime.now().isoformat(),
            data_model={dm.as_reference(): dm.as_request() for dm in cdf_data_models},
            views={view.as_reference(): view.as_request() for view in cdf_views},
            containers={container.as_reference(): container.as_request() for container in cdf_containers},
            spaces={space.space: space.as_request() for space in cdf_spaces},
            node_types={node: node for node in nodes},
        )

    def _create_deployment_plan(self) -> DeploymentPlan:
        """Compare local vs cdf and create deployment plan."""
        return DeploymentPlan(
            spaces=self._plan_spaces(),
            containers=self._plan_containers(),
            views=self._plan_views(),
            data_models=self._plan_data_models(),
            nodes=self._plan_nodes(),
        )

    def _plan_resources(
        self,
        resource_type: DataModelingResource,
        local_items: list[T_Item],
        cdf_items: list[T_Item],
        key_func: Callable[[T_Item], Any],
        resource_id_func: Callable[[T_Item], ReferenceObject | str],
        diff_func: Callable[[T_Item, T_Item], list[PropertyChange]],
    ) -> ResourceDeploymentPlan[T_Item]:
        """Generic method to create deployment plan for any resource type.

        Args:
            resource_type: Type of resource being planned
            local_items: Local resources from data_model
            cdf_items: CDF resources fetched from cloud
            key_func: Function to extract unique key from resource
            resource_id_func: Function to extract resource_id for ResourceDiff
            diff_func: Function to diff two resources
        """
        local_map = {key_func(item): item for item in local_items}
        cdf_map = {key_func(item): item for item in cdf_items}

        to_create: list[ResourceDiff[T_Item]] = []
        to_update: list[ResourceDiff[T_Item]] = []
        unchanged: list[ResourceDiff[T_Item]] = []
        to_recreate: list[ResourceDiff[T_Item]] = []

        for key, local_item in local_map.items():
            resource_id = resource_id_func(local_item)

            if key not in cdf_map:
                to_create.append(
                    ResourceDiff(
                        resource_type=resource_type,
                        resource_id=resource_id,
                        action="create",
                        changes=[],
                        new_value=local_item,
                        old_value=None,
                    )
                )
            else:
                cdf_item = cdf_map[key]
                changes = diff_func(local_item, cdf_item)
                if changes:
                    to_update.append(
                        ResourceDiff(
                            resource_type=resource_type,
                            resource_id=resource_id,
                            action="update",
                            changes=changes,
                            new_value=local_item,
                            old_value=cdf_item,
                        )
                    )
                else:
                    unchanged.append(
                        ResourceDiff(
                            resource_type=resource_type,
                            resource_id=resource_id,
                            action="unchanged",
                            changes=[],
                            new_value=local_item,
                            old_value=cdf_item,
                        )
                    )

        return ResourceDeploymentPlan(
            to_create=to_create, to_update=to_update, to_recreate=to_recreate, unchanged=unchanged
        )

    def _plan_spaces(self) -> ResourceDeploymentPlan[SpaceRequest]:
        """Create deployment plan for spaces."""
        return self._plan_resources(
            resource_type="space",
            local_items=self.data_model.spaces,
            cdf_items=self._snapshot.spaces if self._snapshot else {},
            key_func=lambda s: s.space,
            resource_id_func=lambda s: s.space,
            diff_func=self._diff_spaces,
        )

    def _plan_containers(self) -> ResourceDeploymentPlan[ContainerRequest]:
        """Create deployment plan for containers."""
        return self._plan_resources(
            resource_type="container",
            local_items=self.data_model.containers,
            cdf_items=self._cdf_schema.containers if self._cdf_schema else [],
            key_func=lambda c: (c.space, c.external_id),
            resource_id_func=lambda c: c.as_reference(),
            diff_func=self._diff_containers,
        )

    def _plan_views(self) -> ResourceDeploymentPlan[ViewRequest]:
        """Create deployment plan for views."""
        # TODO: Implement similar to containers
        return ResourceDeploymentPlan(to_create=[], to_update=[], to_recreate=[], unchanged=[])

    def _plan_data_models(self) -> ResourceDeploymentPlan[DataModelRequest]:
        """Create deployment plan for data models."""
        # TODO: Implement similar to containers
        return ResourceDeploymentPlan(to_create=[], to_update=[], to_recreate=[], unchanged=[])

    def _plan_nodes(self) -> ResourceDeploymentPlan[NodeReference]:
        """Create deployment plan for nodes."""
        # TODO: Implement when node API is available
        return ResourceDeploymentPlan(to_create=[], to_update=[], to_recreate=[], unchanged=[])

    def _create_field_change(
        self, field_path: str, local_value: Any, cdf_value: Any, severity: SeverityType = "safe"
    ) -> PropertyChange | None:
        """Create a PropertyChange if values differ, otherwise return None."""
        if local_value == cdf_value:
            return None

        return PropertyChange(
            field_path=field_path,
            change_type="modified",
            severity=severity,
            description=f"{field_path} changed from '{cdf_value}' to '{local_value}'",
        )

    def _diff_dict_items(
        self,
        field_prefix: str,
        local_dict: dict,
        cdf_dict: dict,
        add_severity: SeverityType = "safe",
        remove_severity: SeverityType = "breaking",
        modify_severity: SeverityType = "breaking",
    ) -> list[PropertyChange]:
        """Compare two dictionaries and return changes for added/removed/modified keys.

        Args:
            field_prefix: Prefix for the field path (e.g., "properties", "constraints")
            local_dict: Local dictionary
            cdf_dict: CDF dictionary
            add_severity: Severity for added items
            remove_severity: Severity for removed items
            modify_severity: Severity for modified items
        """
        changes = []
        local_keys = set(local_dict.keys())
        cdf_keys = set(cdf_dict.keys())

        # Added items
        for key in local_keys - cdf_keys:
            changes.append(
                PropertyChange(
                    field_path=f"{field_prefix}.{key}",
                    change_type="added",
                    severity=add_severity,
                    description=f"{field_prefix.capitalize()} '{key}' added",
                )
            )

        # Removed items
        for key in cdf_keys - local_keys:
            changes.append(
                PropertyChange(
                    field_path=f"{field_prefix}.{key}",
                    change_type="removed",
                    severity=remove_severity,
                    description=f"{field_prefix.capitalize()} '{key}' removed",
                )
            )

        # Modified items
        for key in local_keys & cdf_keys:
            if local_dict[key] != cdf_dict[key]:
                changes.append(
                    PropertyChange(
                        field_path=f"{field_prefix}.{key}",
                        change_type="modified",
                        severity=modify_severity,
                        description=f"{field_prefix.capitalize()} '{key}' modified",
                    )
                )

        return changes

    def _diff_spaces(self, local: SpaceRequest, cdf: SpaceRequest) -> list[PropertyChange]:
        """Compare two spaces and return changes."""
        changes = []

        if change := self._create_field_change("name", local.name, cdf.name):
            changes.append(change)

        if change := self._create_field_change("description", local.description, cdf.description):
            changes.append(change)

        return changes

    def _diff_containers(self, local: ContainerRequest, cdf: ContainerRequest) -> list[PropertyChange]:
        """Compare two containers and return changes."""
        changes = []

        # Check primary properties
        if change := self._create_field_change("name", local.name, cdf.name):
            changes.append(change)

        if change := self._create_field_change("description", local.description, cdf.description):
            changes.append(change)

        if change := self._create_field_change("used_for", local.used_for, cdf.used_for, severity="breaking"):
            changes.append(change)

        # Check properties (added/removed/modified)
        changes.extend(self._diff_dict_items("properties", local.properties, cdf.properties))

        # Check constraints (added/removed)
        changes.extend(
            self._diff_dict_items(
                "constraints",
                local.constraints or {},
                cdf.constraints or {},
                add_severity="safe",
                remove_severity="breaking",
            )
        )

        # Check indexes (added/removed)
        changes.extend(
            self._diff_dict_items(
                "indexes",
                local.indexes or {},
                cdf.indexes or {},
                add_severity="safe",
                remove_severity="safe",
            )
        )

        return changes

    def _analyze_changes(self, plan: DeploymentPlan) -> None:
        """Analyze changes and collect issues."""
        # Collect all changes across all resource types
        all_changes: list[ResourceDiff[Any]] = []
        resource_plans: list[ResourceDeploymentPlan[Any]] = [
            plan.spaces,
            plan.containers,
            plan.views,
            plan.data_models,
            plan.nodes,
        ]
        for resource_plan in resource_plans:
            all_changes.extend(resource_plan.to_create + resource_plan.to_update + resource_plan.to_recreate)

        # Check for breaking changes
        for resource_diff in all_changes:
            for change in resource_diff.changes:
                if change.severity == "breaking":
                    self.issues.append(
                        ImplementationWarning(
                            message=f"Breaking change in {resource_diff.resource_type} "
                            f"{resource_diff.resource_id}: {change.description}",
                            fix="Review the breaking changes and ensure data migration is planned.",
                        )
                    )

    def _should_proceed(self, plan: DeploymentPlan) -> bool:
        """Check if deployment should proceed based on options and issues."""
        # Check if there are any changes
        if not plan.has_changes():
            return False

        # Check if there are blocking issues (errors)
        if any(isinstance(issue, ModelSyntaxError | ConsistencyError) for issue in self.issues):
            return False

        # Check if warnings should block deployment
        if not self.options.ignore_warnings and any(isinstance(issue, ImplementationWarning) for issue in self.issues):
            return False

        return True

    def _apply_changes(self, plan: DeploymentPlan) -> DeploymentResult:
        """Apply the deployment plan to CDF."""
        applied_changes: list[ResourceDiff[Any]] = []
        failed_changes: list[ResourceDiff[Any]] = []

        # TODO: Implement actual API calls to create/update resources
        # Order matters: spaces -> containers -> views -> data models -> nodes

        # For now, return a mock result
        return DeploymentResult(
            success=True,
            plan=plan,
            applied_changes=applied_changes,
            failed_changes=failed_changes,
            snapshot=self._snapshot,
            issues=self.issues,
            dry_run=False,
        )

    def _rollback(self, snapshot: DeploymentSnapshot) -> bool:
        """Rollback to previous state using snapshot."""
        # TODO: Implement rollback logic
        return False
