from dataclasses import dataclass
from typing import Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel

from cognite.neat._client import NeatClient
from cognite.neat._data_model._shared import OnSuccess
from cognite.neat._issues import Issue, IssueList

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
SeverityType: TypeAlias = Literal["safe", "breaking"]


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
    resource_id: ReferenceObject
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
    """Stores the cloud state before deployment for rollback."""

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
        self.issues: list[Issue] = []

    def run(self) -> None:
        """Execute the success handler on the data model."""
        # For each resource type (space, container, view, data model, node),
        # Categorize them into to_create, to_update, unchanged, to_recreate
        # The to_update items should have a change list indicating what changed.
        # We should analyze the change list to see if there are any issues.

        # Then in deploy mode, we should check for dry-run
        # If not store the previous state for rollback. Then, apply the changes
        raise NotImplementedError()
