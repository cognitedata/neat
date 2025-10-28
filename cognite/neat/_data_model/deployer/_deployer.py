from dataclasses import dataclass
from datetime import datetime, timezone

from cognite.neat._client import NeatClient
from cognite.neat._data_model._shared import OnSuccessResultProducer
from cognite.neat._data_model.deployer.data_classes import DataModelEndpoint, ResourceChange, SeverityType, T_Resource
from cognite.neat._data_model.models.dms import RequestSchema, T_Reference
from cognite.neat._utils.http_client import ItemBody, ItemsRequest

from .data_classes import AppliedChanges, DeploymentResult, ResourceDeploymentPlan, SchemaSnapshot


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
        # Step 1: Fetch current CDF state
        snapshot = self._fetch_cdf_state(data_model)

        # Step 2: Create deployment plan by comparing local vs cdf
        plan = self._create_deployment_plan(snapshot, data_model)

        if not self._should_proceed(plan):
            # Step 3: Check if deployment should proceed
            return DeploymentResult(status="failure", plan=plan, snapshot=snapshot)
        elif self.options.dry_run:
            # Step 4: If dry-run, return plan without applying
            return DeploymentResult(status="pending", plan=plan, snapshot=snapshot)

        # Step 5: Apply changes
        changes = self._apply_changes(plan)

        # Step 6: Rollback if failed and auto_rollback is enabled
        if not changes.is_success and self.options.auto_rollback:
            recovery = self._apply_changes(changes.as_recovery_plan())
            return DeploymentResult(
                status="success", plan=plan, snapshot=snapshot, responses=changes, recovery=recovery
            )

        return DeploymentResult(status="success", plan=plan, snapshot=snapshot, responses=changes)

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
        return [
            self._create_resource_plan(snapshot.spaces, data_model.spaces, "spaces"),
            self._create_resource_plan(snapshot.containers, data_model.containers, "containers"),
            self._create_resource_plan(snapshot.views, data_model.views, "views"),
            self._create_resource_plan(snapshot.data_model, [data_model.data_model], "datamodels"),
        ]

    def _create_resource_plan(
        self, existing: dict[T_Reference, T_Resource], desired: list[T_Resource], endpoint: DataModelEndpoint
    ) -> ResourceDeploymentPlan:
        resources: list[ResourceChange[T_Reference, T_Resource]] = []
        for resource in desired:
            ref = resource.as_reference()
            if ref not in existing:
                resources.append(ResourceChange(resource_id=ref, new_value=resource))
                continue
            cdf_resource = existing[ref]
            diffs = resource.diff(cdf_resource)
            resources.append(ResourceChange(resource_id=ref, new_value=resource, old_value=cdf_resource, changes=diffs))

        return ResourceDeploymentPlan(endpoint=endpoint, resources=resources)

    def _should_proceed(self, plan: list[ResourceDeploymentPlan]) -> bool:
        # Placeholder for actual implementation
        return True

    def _apply_changes(self, plan: list[ResourceDeploymentPlan]) -> AppliedChanges:
        config = self.client.config
        for resource in plan:
            to_delete = [resource.resource_id for resource in resource.to_delete]
            responses = self.client.http_client.request_with_retries(
                ItemsRequest(
                    endpoint_url=config.create_api_url(f"/models/{resource.endpoint}/delete"),
                    method="POST",
                    body=ItemBody(items=to_delete),
                    as_id=lambda x: x,
                )
            )
            for response in responses:
                raise NotImplementedError()
            to_upsert = [change.new_value for change in resource.to_upsert]
            responses = self.client.http_client.request_with_retries(
                ItemsRequest(
                    endpoint_url=config.create_api_url(f"/models/{resource.endpoint}"),
                    method="POST",
                    body=ItemBody(items=to_upsert),
                    as_id=lambda x: x.as_reference(),
                )
            )
            for response in responses:
                # Validate output matches input. Data Modeling has false updates.
                raise NotImplementedError()
            # If failure abort
        return AppliedChanges(status="success", created=[], updated=[], deletions=[])
