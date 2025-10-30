from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, cast

from cognite.neat._client import NeatClient
from cognite.neat._data_model.models.dms import RequestSchema, T_DataModelResource, T_ResourceId

from ._differ import ItemDiffer
from ._differ_container import ContainerDiffer
from ._differ_data_model import DataModelDiffer
from ._differ_space import SpaceDiffer
from ._differ_view import ViewDiffer
from .data_classes import (
    AppliedChanges,
    DataModelEndpoint,
    DeploymentResult,
    ResourceChange,
    ResourceDeploymentPlan,
    SchemaSnapshot,
    SeverityType,
)


@dataclass
class DeploymentOptions:
    """Configuration options for deployment.

    Attributes:
        dry_run (bool): If True, the deployment will be simulated without applying changes. Defaults to True.
        auto_rollback (bool): If True, automatically roll back changes if deployment fails. Defaults to True.
        max_severity (SeverityType): Maximum allowed severity of changes to proceed with deployment.
            Defaults to SeverityType.SAFE.
        modus_operandi (Literal["partial", "overwrite"]): Deployment mode. If "partial", only add/modify resources
            specified in the data model. If "overwrite", remove resources not present in the data model.
            Defaults to "partial".
    """

    dry_run: bool = True
    auto_rollback: bool = True
    max_severity: SeverityType = SeverityType.SAFE
    modus_operandi: Literal["partial", "overwrite"] = "partial"


class SchemaDeployer:
    def __init__(self, client: NeatClient, options: DeploymentOptions | None = None) -> None:
        self.client: NeatClient = client
        self.options: DeploymentOptions = options or DeploymentOptions()
        self._results: DeploymentResult | None = None

    @property
    def results(self) -> DeploymentResult:
        if self._results is None:
            raise RuntimeError("SchemaDeployer has not been run yet.")
        return self._results

    def run(self, data_model: RequestSchema) -> None:
        self._results = self.deploy(data_model)

    def deploy(self, data_model: RequestSchema) -> DeploymentResult:
        # Step 1: Fetch current CDF state
        snapshot = self.fetch_cdf_state(data_model)

        # Step 2: Create deployment plan by comparing local vs cdf
        plan = self.create_deployment_plan(snapshot, data_model)

        if not self.should_proceed_to_deploy(plan):
            # Step 3: Check if deployment should proceed
            return DeploymentResult(status="failure", plan=plan, snapshot=snapshot)
        elif self.options.dry_run:
            # Step 4: If dry-run, return plan without applying
            return DeploymentResult(status="pending", plan=plan, snapshot=snapshot)

        # Step 5: Apply changes
        changes = self.apply_changes(plan)

        # Step 6: Rollback if failed and auto_rollback is enabled
        if not changes.is_success and self.options.auto_rollback:
            recovery = self.apply_changes(changes.as_recovery_plan())
            return DeploymentResult(
                status="success", plan=plan, snapshot=snapshot, responses=changes, recovery=recovery
            )
        status: Literal["success", "failure", "partial", "pending"] = "success" if changes.is_success else "partial"
        return DeploymentResult(status=status, plan=plan, snapshot=snapshot, responses=changes)

    def fetch_cdf_state(self, data_model: RequestSchema) -> SchemaSnapshot:
        now = datetime.now(tz=timezone.utc)
        space_ids = [space.as_reference() for space in data_model.spaces]
        cdf_spaces = self.client.spaces.retrieve(space_ids)

        container_refs = [c.as_reference() for c in data_model.containers]
        cdf_containers = self.client.containers.retrieve(container_refs)

        view_refs = [v.as_reference() for v in data_model.views]
        cdf_views = self.client.views.retrieve(view_refs)

        dm_ref = data_model.data_model.as_reference()
        cdf_data_models = self.client.data_models.retrieve([dm_ref])

        nodes = [node_type for view in cdf_views for node_type in view.node_types]
        return SchemaSnapshot(
            timestamp=now,
            data_model={dm.as_reference(): dm.as_request() for dm in cdf_data_models},
            views={view.as_reference(): view.as_request() for view in cdf_views},
            containers={container.as_reference(): container.as_request() for container in cdf_containers},
            spaces={space.as_reference(): space.as_request() for space in cdf_spaces},
            node_types={node: node for node in nodes},
        )

    def create_deployment_plan(
        self, snapshot: SchemaSnapshot, data_model: RequestSchema
    ) -> list[ResourceDeploymentPlan]:
        return [
            self._create_resource_plan(snapshot.spaces, data_model.spaces, "spaces", SpaceDiffer()),
            self._create_resource_plan(snapshot.containers, data_model.containers, "containers", ContainerDiffer()),
            self._create_resource_plan(snapshot.views, data_model.views, "views", ViewDiffer()),
            self._create_resource_plan(snapshot.data_model, [data_model.data_model], "datamodels", DataModelDiffer()),
        ]

    @classmethod
    def _create_resource_plan(
        cls,
        current_resources: dict[T_ResourceId, T_DataModelResource],
        new_resources: list[T_DataModelResource],
        endpoint: DataModelEndpoint,
        differ: ItemDiffer[T_DataModelResource],
    ) -> ResourceDeploymentPlan[T_ResourceId, T_DataModelResource]:
        resources: list[ResourceChange[T_ResourceId, T_DataModelResource]] = []
        for new_resource in new_resources:
            # We know that .as_reference() will return T_ResourceId
            ref = cast(T_ResourceId, new_resource.as_reference())
            if ref not in current_resources:
                resources.append(ResourceChange(resource_id=ref, new_value=new_resource))
                continue
            current_resource = current_resources[ref]
            diffs = differ.diff(current_resource, new_resource)
            resources.append(
                ResourceChange(resource_id=ref, new_value=new_resource, old_value=current_resource, changes=diffs)
            )

        return ResourceDeploymentPlan(endpoint=endpoint, resources=resources)

    def should_proceed_to_deploy(self, plan: list[ResourceDeploymentPlan]) -> bool:
        # Placeholder for actual implementation
        return True

    def apply_changes(self, plan: list[ResourceDeploymentPlan]) -> AppliedChanges:
        raise NotImplementedError()
