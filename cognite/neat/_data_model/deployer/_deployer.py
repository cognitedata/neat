from dataclasses import dataclass
from datetime import datetime, timezone

from cognite.neat._client import NeatClient
from cognite.neat._data_model._shared import OnSuccessResultProducer
from cognite.neat._data_model.deployer.data_classes import SeverityType
from cognite.neat._data_model.models.dms import RequestSchema

from .data_classes import DeploymentResult, ResourceDeploymentPlan, SchemaSnapshot


@dataclass
class DeploymentOptions:
    """Configuration options for deployment."""

    dry_run: bool = True
    auto_rollback: bool = True
    max_severity: SeverityType = "safe"


class SchemaDeployer(OnSuccessResultProducer):
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
        snapshot = self._fetch_cdf_state(data_model)

        # Step 2: Create deployment plan by comparing local vs cdf
        plan = self._create_deployment_plan(snapshot, data_model)

        # Step 3: Check if deployment should proceed
        if not self._should_proceed(plan):
            return DeploymentResult(status="failure", plan=plan, snapshot=snapshot)

        # Step 4: If dry-run, return plan without applying
        elif self.options.dry_run:
            return DeploymentResult(status="pending", plan=plan, snapshot=snapshot)

        # Step 5: Apply changes
        result = self._apply_changes(plan)

        # Step 6: Rollback if failed and auto_rollback is enabled
        if not result.is_success and self.options.auto_rollback:
            self._apply_changes(snapshot.as_plan(drop_data=True))

        return result

    def _fetch_cdf_state(self, data_model: RequestSchema) -> SchemaSnapshot:
        now = datetime.now(tz=timezone.utc)
        space_ids = [space.space for space in data_model.spaces]
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
            spaces={space.space: space.as_request() for space in cdf_spaces},
            node_types={node: node for node in nodes},
        )

    def _create_deployment_plan(
        self, snapshot: SchemaSnapshot, data_model: RequestSchema
    ) -> list[ResourceDeploymentPlan]:
        # Placeholder for actual implementation
        return []

    def _should_proceed(self, plan: list[ResourceDeploymentPlan]) -> bool:
        # Placeholder for actual implementation
        return True

    def _apply_changes(self, plan: list[ResourceDeploymentPlan]) -> DeploymentResult:
        raise NotImplementedError()
