from dataclasses import dataclass
from datetime import datetime
from typing import Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel

from cognite.neat._client import NeatClient
from cognite.neat._data_model._shared import OnSuccess
from cognite.neat._issues import ConsistencyError, ImplementationWarning, IssueList, ModelSyntaxError

from ._container import ContainerRequest
from ._data_model import DataModelRequest
from ._references import NodeReference, ReferenceObject
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


@dataclass
class DeploymentSnapshot:
    """Stores the cdf state before deployment for rollback."""

    timestamp: str
    schema: RequestSchema


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


class SchemaDeployer(OnSuccess):
    def __init__(self, data_model: RequestSchema, client: NeatClient, options: DeploymentOptions | None = None) -> None:
        super().__init__(data_model)
        self.data_model: RequestSchema = data_model
        self.client: NeatClient = client
        self.options: DeploymentOptions = options or DeploymentOptions()
        self.issues: IssueList = IssueList()
        self._cdf_schema: RequestSchema | None = None
        self._snapshot: DeploymentSnapshot | None = None

    def run(self) -> DeploymentResult:
        """Execute the deployment with dry-run and rollback support."""
        # Step 1: Fetch current cdf state
        self._cdf_schema = self._fetch_cdf_state()

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

        # Step 6: Create snapshot for rollback
        if self.options.auto_rollback:
            self._snapshot = self._create_snapshot()

        # Step 7: Apply changes
        result = self._apply_changes(plan)

        # Step 8: Rollback if failed and auto_rollback is enabled
        if not result.success and self.options.auto_rollback and self._snapshot:
            self._rollback(self._snapshot)

        return result

    def _fetch_cdf_state(self) -> RequestSchema:
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
        return RequestSchema(
            data_model=cdf_data_models[0].as_request() if cdf_data_models else None,
            views=[v.as_request() for v in cdf_views],
            containers=[c.as_request() for c in cdf_containers],
            spaces=[s.as_request() for s in cdf_spaces],
            node_types=nodes,
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

    def _plan_spaces(self) -> ResourceDeploymentPlan[SpaceRequest]:
        """Create deployment plan for spaces."""
        local_spaces = {s.space: s for s in self.data_model.spaces}
        cdf_spaces = {s.space: s for s in (self._cdf_schema.spaces if self._cdf_schema else [])}

        to_create = []
        to_update = []
        unchanged = []
        to_recreate = []

        for space_id, local_space in local_spaces.items():
            if space_id not in cdf_spaces:
                to_create.append(
                    ResourceDiff(
                        resource_type="space",
                        resource_id=space_id,
                        action="create",
                        changes=[],
                        new_value=local_space,
                        old_value=None,
                    )
                )
            else:
                cdf_space = cdf_spaces[space_id]
                changes = self._diff_spaces(local_space, cdf_space)
                if changes:
                    to_update.append(
                        ResourceDiff(
                            resource_type="space",
                            resource_id=space_id,
                            action="update",
                            changes=changes,
                            new_value=local_space,
                            old_value=cdf_space,
                        )
                    )
                else:
                    unchanged.append(
                        ResourceDiff(
                            resource_type="space",
                            resource_id=space_id,
                            action="unchanged",
                            changes=[],
                            new_value=local_space,
                            old_value=cdf_space,
                        )
                    )

        return ResourceDeploymentPlan(
            to_create=to_create, to_update=to_update, to_recreate=to_recreate, unchanged=unchanged
        )

    def _plan_containers(self) -> ResourceDeploymentPlan[ContainerRequest]:
        """Create deployment plan for containers."""
        local_containers = {(c.space, c.external_id): c for c in self.data_model.containers}
        cdf_containers = {
            (c.space, c.external_id): c for c in (self._cdf_schema.containers if self._cdf_schema else [])
        }

        to_create = []
        to_update = []
        unchanged = []
        to_recreate = []

        for container_id, local_container in local_containers.items():
            ref = local_container.as_reference()
            if container_id not in cdf_containers:
                to_create.append(
                    ResourceDiff(
                        resource_type="container",
                        resource_id=ref,
                        action="create",
                        changes=[],
                        new_value=local_container,
                        old_value=None,
                    )
                )
            else:
                cdf_container = cdf_containers[container_id]
                changes = self._diff_containers(local_container, cdf_container)
                if changes:
                    to_update.append(
                        ResourceDiff(
                            resource_type="container",
                            resource_id=ref,
                            action="update",
                            changes=changes,
                            new_value=local_container,
                            old_value=cdf_container,
                        )
                    )
                else:
                    unchanged.append(
                        ResourceDiff(
                            resource_type="container",
                            resource_id=ref,
                            action="unchanged",
                            changes=[],
                            new_value=local_container,
                            old_value=cdf_container,
                        )
                    )

        return ResourceDeploymentPlan(
            to_create=to_create, to_update=to_update, to_recreate=to_recreate, unchanged=unchanged
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

    def _diff_spaces(self, local: SpaceRequest, cdf: SpaceRequest) -> list[PropertyChange]:
        """Compare two spaces and return changes."""
        changes = []

        if local.name != cdf.name:
            changes.append(
                PropertyChange(
                    field_path="name",
                    change_type="modified",
                    severity="safe",
                    description=f"Name changed from '{cdf.name}' to '{local.name}'",
                )
            )

        if local.description != cdf.description:
            changes.append(
                PropertyChange(
                    field_path="description",
                    change_type="modified",
                    severity="safe",
                    description=f"Description changed from '{cdf.description}' to '{local.description}'",
                )
            )

        return changes

    def _diff_containers(self, local: ContainerRequest, cdf: ContainerRequest) -> list[PropertyChange]:
        """Compare two containers and return changes."""
        changes = []

        # Check primary properties
        if local.name != cdf.name:
            changes.append(
                PropertyChange(
                    field_path="name",
                    change_type="modified",
                    severity="safe",
                    description=f"Name changed from '{cdf.name}' to '{local.name}'",
                )
            )

        if local.description != cdf.description:
            changes.append(
                PropertyChange(
                    field_path="description",
                    change_type="modified",
                    severity="safe",
                    description="Description changed",
                )
            )

        if local.used_for != cdf.used_for:
            changes.append(
                PropertyChange(
                    field_path="used_for",
                    change_type="modified",
                    severity="breaking",
                    description=f"used_for changed from '{cdf.used_for}' to '{local.used_for}'",
                )
            )

        # Check properties
        local_props = set(local.properties.keys())
        cdf_props = set(cdf.properties.keys())

        for prop_name in local_props - cdf_props:
            changes.append(
                PropertyChange(
                    field_path=f"properties.{prop_name}",
                    change_type="added",
                    severity="safe",
                    description=f"Property '{prop_name}' added",
                )
            )

        for prop_name in cdf_props - local_props:
            changes.append(
                PropertyChange(
                    field_path=f"properties.{prop_name}",
                    change_type="removed",
                    severity="breaking",
                    description=f"Property '{prop_name}' removed",
                )
            )

        for prop_name in local_props & cdf_props:
            local_prop = local.properties[prop_name]
            cdf_prop = cdf.properties[prop_name]
            if local_prop != cdf_prop:
                changes.append(
                    PropertyChange(
                        field_path=f"properties.{prop_name}",
                        change_type="modified",
                        severity="breaking",
                        description=f"Property '{prop_name}' modified",
                    )
                )

        # Check constraints
        local_constraints = set((local.constraints or {}).keys())
        cdf_constraints = set((cdf.constraints or {}).keys())

        for constraint_name in local_constraints - cdf_constraints:
            changes.append(
                PropertyChange(
                    field_path=f"constraints.{constraint_name}",
                    change_type="added",
                    severity="safe",
                    description=f"Constraint '{constraint_name}' added",
                )
            )

        for constraint_name in cdf_constraints - local_constraints:
            changes.append(
                PropertyChange(
                    field_path=f"constraints.{constraint_name}",
                    change_type="removed",
                    severity="breaking",
                    description=f"Constraint '{constraint_name}' removed",
                )
            )

        # Check indexes
        local_indexes = set((local.indexes or {}).keys())
        cdf_indexes = set((cdf.indexes or {}).keys())

        for index_name in local_indexes - cdf_indexes:
            changes.append(
                PropertyChange(
                    field_path=f"indexes.{index_name}",
                    change_type="added",
                    severity="safe",
                    description=f"Index '{index_name}' added",
                )
            )

        for index_name in cdf_indexes - local_indexes:
            changes.append(
                PropertyChange(
                    field_path=f"indexes.{index_name}",
                    change_type="removed",
                    severity="safe",
                    description=f"Index '{index_name}' removed",
                )
            )

        return changes

    def _analyze_changes(self, plan: DeploymentPlan) -> None:
        """Analyze changes and collect issues."""
        # Collect all changes across all resource types
        all_changes: list[ResourceDiff] = []
        all_changes.extend(plan.spaces.to_create + plan.spaces.to_update + plan.spaces.to_recreate)
        all_changes.extend(plan.containers.to_create + plan.containers.to_update + plan.containers.to_recreate)
        all_changes.extend(plan.views.to_create + plan.views.to_update + plan.views.to_recreate)
        all_changes.extend(plan.data_models.to_create + plan.data_models.to_update + plan.data_models.to_recreate)
        all_changes.extend(plan.nodes.to_create + plan.nodes.to_update + plan.nodes.to_recreate)

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
        has_changes = any(
            [
                plan.spaces.to_create or plan.spaces.to_update or plan.spaces.to_recreate,
                plan.containers.to_create or plan.containers.to_update or plan.containers.to_recreate,
                plan.views.to_create or plan.views.to_update or plan.views.to_recreate,
                plan.data_models.to_create or plan.data_models.to_update or plan.data_models.to_recreate,
                plan.nodes.to_create or plan.nodes.to_update or plan.nodes.to_recreate,
            ]
        )

        if not has_changes:
            return False

        # Check if there are blocking issues (errors)
        if any(isinstance(issue, (ModelSyntaxError, ConsistencyError)) for issue in self.issues):
            return False

        # Check if warnings should block deployment
        if not self.options.ignore_warnings and any(isinstance(issue, ImplementationWarning) for issue in self.issues):
            return False

        return True

    def _create_snapshot(self) -> DeploymentSnapshot:
        """Create snapshot of cdf state for rollback."""
        return DeploymentSnapshot(
            timestamp=datetime.now().isoformat(),
            schema=self._cdf_schema,
        )

    def _apply_changes(self, plan: DeploymentPlan) -> DeploymentResult:
        """Apply the deployment plan to CDF."""
        applied_changes = []
        failed_changes = []

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
