from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from typing import cast

from cognite.neat._client import NeatClient
from cognite.neat._data_model._shared import OnSuccessResultProducer
from cognite.neat._data_model.models.dms import (
    ContainerReference,
    ContainerRequest,
    DataModelBody,
    RequestSchema,
    T_DataModelResource,
    T_ResourceId,
    ViewReference,
)
from cognite.neat._utils.collection import chunker_sequence
from cognite.neat._utils.http_client import (
    FailedRequestItems,
    FailedResponseItems,
    ItemIDBody,
    ItemsRequest,
    SuccessResponseItems,
)
from cognite.neat._utils.http_client._data_classes import APIResponse
from cognite.neat._utils.useful_types import ModusOperandi, T_Reference

from ._differ import ItemDiffer
from ._differ_container import ContainerDiffer
from ._differ_data_model import DataModelDiffer
from ._differ_space import SpaceDiffer
from ._differ_view import ViewDiffer
from .data_classes import (
    AddedField,
    AppliedChanges,
    ChangedFieldResult,
    ChangeResult,
    ContainerDeploymentPlan,
    DataModelEndpoint,
    DeploymentResult,
    FieldChange,
    FieldChanges,
    RemovedField,
    ResourceChange,
    ResourceDeploymentPlan,
    ResourceDeploymentPlanList,
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
        modus_operandi (ModusOperandi): Deployment mode. If "additive", only add/modify resources
            specified in the data model. If "rebuild", remove resources not present in the data model.
            Defaults to "additive".
    """

    dry_run: bool = True
    auto_rollback: bool = True
    drop_data: bool = False
    max_severity: SeverityType = SeverityType.SAFE
    modus_operandi: ModusOperandi = "additive"


class SchemaDeployer(OnSuccessResultProducer):
    INDEX_DELETE_BATCH_SIZE = 10
    CONSTRAINT_DELETE_BATCH_SIZE = 10

    def __init__(self, client: NeatClient, options: DeploymentOptions | None = None) -> None:
        super().__init__()
        self.client: NeatClient = client
        self.options: DeploymentOptions = options or DeploymentOptions()

    def run(self, data_model: RequestSchema) -> None:
        if self._results is not None:
            raise RuntimeError("SchemaDeployer has already been run.")
        self._results = self.deploy(data_model)

    def deploy(self, data_model: RequestSchema) -> DeploymentResult:
        # Step 1: Fetch current CDF state
        snapshot = self.fetch_cdf_state(data_model)

        # Step 2: Create deployment plan by comparing local vs cdf
        plan = self.create_deployment_plan(snapshot, data_model)

        # Step 3: Adjust plan based on modus operandi
        if self.options.modus_operandi == "additive":
            # Filter out deletions and removals in additive mode
            plan = plan.consolidate_changes()
        elif self.options.modus_operandi == "rebuild":
            # Breaking changes are forced by deleting and recreating resources
            # Containers are treated as additive unless drop_data is specified
            plan = plan.force_changes(self.options.drop_data)
        else:
            raise NotImplementedError(f"Unsupported modus operandi: {self.options.modus_operandi!r}")

        if not self.should_proceed_to_deploy(plan):
            # Step 4: Check if deployment should proceed
            return DeploymentResult(status="failure", plan=list(plan), snapshot=snapshot)
        elif self.options.dry_run:
            # Step 5: If dry-run, return plan without applying
            return DeploymentResult(status="pending", plan=list(plan), snapshot=snapshot)

        # Step 6: Apply changes
        changes = self.apply_changes(plan)

        # Step 7: Rollback if failed and auto_rollback is enabled
        if not changes.is_success and self.options.auto_rollback:
            recovery = self.apply_changes(changes.as_recovery_plan())
            return DeploymentResult(
                status="success", plan=list(plan), snapshot=snapshot, responses=changes, recovery=recovery
            )
        return DeploymentResult(
            status="success" if changes.is_success else "partial", plan=list(plan), snapshot=snapshot, responses=changes
        )

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

    def create_deployment_plan(self, snapshot: SchemaSnapshot, data_model: RequestSchema) -> ResourceDeploymentPlanList:
        return ResourceDeploymentPlanList(
            [
                self._create_resource_plan(snapshot.spaces, data_model.spaces, "spaces", SpaceDiffer()),
                self._create_resource_plan(
                    snapshot.containers,
                    data_model.containers,
                    "containers",
                    ContainerDiffer(),
                    ContainerDeploymentPlan,
                    skip_criteria=partial(self._skip_resource, model_space=data_model.data_model.space),
                ),
                self._create_resource_plan(
                    snapshot.views,
                    data_model.views,
                    "views",
                    ViewDiffer(
                        current_container_map=snapshot.containers,
                        new_container_map={container.as_reference(): container for container in data_model.containers},
                    ),
                    skip_criteria=partial(self._skip_resource, model_space=data_model.data_model.space),
                ),
                self._create_resource_plan(
                    snapshot.data_model, [data_model.data_model], "datamodels", DataModelDiffer()
                ),
            ]
        )

    def _create_resource_plan(
        self,
        current_resources: dict[T_ResourceId, T_DataModelResource],
        new_resources: list[T_DataModelResource],
        endpoint: DataModelEndpoint,
        differ: ItemDiffer[T_DataModelResource],
        plan_type: type[ResourceDeploymentPlan[T_ResourceId, T_DataModelResource]] = ResourceDeploymentPlan,
        skip_criteria: Callable[[T_ResourceId], str | None] | None = None,
    ) -> ResourceDeploymentPlan[T_ResourceId, T_DataModelResource]:
        resources: list[ResourceChange[T_ResourceId, T_DataModelResource]] = []
        for new_resource in new_resources:
            # We know that .as_reference() will return T_ResourceId
            ref = cast(T_ResourceId, new_resource.as_reference())
            if skip_criteria is not None and (reason := skip_criteria(ref)):
                resources.append(ResourceChange(resource_id=ref, new_value=None, current_value=None, message=reason))
                continue
            if ref not in current_resources:
                resources.append(ResourceChange(resource_id=ref, new_value=new_resource))
                continue
            current_resource = current_resources[ref]
            diffs = differ.diff(current_resource, new_resource)
            if (
                isinstance(current_resource, ContainerRequest)
                and isinstance(new_resource, ContainerRequest)
                and self.options.modus_operandi == "additive"
            ):
                # In additive mode, changes to constraints and indexes require removal and re-adding
                # In rebuild mode, all changes are forced via deletion and re-adding
                diffs = self.remove_readd_modified_indexes_and_constraints(diffs, current_resource, new_resource)
            resources.append(
                ResourceChange(resource_id=ref, new_value=new_resource, current_value=current_resource, changes=diffs)
            )

        return plan_type(endpoint=endpoint, resources=resources)

    @classmethod
    def remove_readd_modified_indexes_and_constraints(
        cls, diffs: list[FieldChange], current_resource: ContainerRequest, new_resource: ContainerRequest
    ) -> list[FieldChange]:
        """Constraints and indexes cannot be modified directly; they must be removed and re-added.

        Args:
            diffs: The list of field changes detected by the differ.
            current_resource: The current state of the container.
            new_resource: The desired state of the container.
        Returns:
            A modified list of field changes with constraints and indexes handled appropriately.
        """
        modified_diffs: list[FieldChange] = []
        for diff in diffs:
            if (diff.field_path.startswith("constraints") or diff.field_path.startswith("indexes")) and isinstance(
                diff, FieldChanges
            ):
                if "." not in diff.field_path:
                    # Should not happen, but just in case
                    raise RuntimeError("Bug in Neat. Malformed field path for constraint/index change.")
                # Field type is either "constraints" or "indexes"
                field_type, identifier, *_ = diff.field_path.split(".", maxsplit=2)
                # Mark for removal
                modified_diffs.append(
                    RemovedField(
                        field_path=f"{field_type}.{identifier}",
                        item_severity=SeverityType.WARNING,
                        current_value=getattr(current_resource, field_type)[identifier],
                    )
                )
                # Mark for addition
                modified_diffs.append(
                    AddedField(
                        field_path=f"{field_type}.{identifier}",
                        item_severity=SeverityType.SAFE,
                        new_value=getattr(new_resource, field_type)[identifier],
                    )
                )
            else:
                modified_diffs.append(diff)
        return modified_diffs

    @classmethod
    def _skip_resource(cls, resource_id: ContainerReference | ViewReference, model_space: str) -> str | None:
        """Checks if a resource should be skipped based on its space.

        Args:
            resource_id: The ID of the resource to check.
            model_space: The space of the data model.

        Returns:
            A reason for skipping if the resource space does not match the model space, otherwise None.
        """
        if resource_id.space != model_space:
            return f"Skipping resource in space '{resource_id.space}' not matching data model space '{model_space}'."
        return None

    def should_proceed_to_deploy(self, plan: Sequence[ResourceDeploymentPlan]) -> bool:
        max_severity_in_plan = SeverityType.max_severity(
            [change.severity for resource_plan in plan for change in resource_plan.resources],
            default=SeverityType.SAFE,
        )
        return max_severity_in_plan.value <= self.options.max_severity.value

    def apply_changes(self, plan: Sequence[ResourceDeploymentPlan]) -> AppliedChanges:
        """Applies the given deployment plan to CDF by making the necessary API calls.

        Args:
            plan (list[ResourceDeploymentPlan]): The deployment plan to apply.

        Returns:
            AppliedChanges: The result of applying the changes.
        """
        applied_changes = AppliedChanges()
        for resource in reversed(plan):
            deletions = self._delete_items(resource)
            applied_changes.deletions.extend(deletions)

        for resource in plan:
            if isinstance(resource, ContainerDeploymentPlan):
                applied_changes.changed_fields.extend(self._remove_container_constraints(resource))
                applied_changes.changed_fields.extend(self._remove_container_indexes(resource))

            creations, updated = self._upsert_items(resource)
            applied_changes.created.extend(creations)
            applied_changes.updated.extend(updated)

            applied_changes.unchanged.extend(resource.unchanged)
            applied_changes.skipped.extend(resource.skip)
        return applied_changes

    def _delete_items(self, resource: ResourceDeploymentPlan) -> list[ChangeResult]:
        to_delete_by_id = {change.resource_id: change for change in resource.to_delete}
        if not to_delete_by_id:
            return []
        responses = self.client.http_client.request_with_retries(
            ItemsRequest(
                endpoint_url=self.client.config.create_api_url(f"/models/{resource.endpoint}/delete"),
                method="POST",
                body=ItemIDBody(items=list(to_delete_by_id.keys())),
            )
        )
        return self._process_resource_responses(responses, to_delete_by_id, resource.endpoint)

    def _upsert_items(self, resource: ResourceDeploymentPlan) -> tuple[list[ChangeResult], list[ChangeResult]]:
        to_upsert = [
            resource_change.new_value for resource_change in resource.to_upsert if resource_change.new_value is not None
        ]
        if not to_upsert:
            return [], []
        responses = self.client.http_client.request_with_retries(
            ItemsRequest(
                endpoint_url=self.client.config.create_api_url(f"/models/{resource.endpoint}"),
                method="POST",
                body=DataModelBody(items=to_upsert),
            )
        )
        to_create_by_id = {rc.resource_id: rc for rc in resource.to_create}
        create_result = self._process_resource_responses(responses, to_create_by_id, resource.endpoint)
        to_update_by_id = {rc.resource_id: rc for rc in resource.to_update}
        update_result = self._process_resource_responses(responses, to_update_by_id, resource.endpoint)
        return create_result, update_result

    def _remove_container_indexes(self, resource: ContainerDeploymentPlan) -> list[ChangedFieldResult]:
        return self._remove_container_fields(
            resource.indexes_to_remove,
            "/models/containers/indexes/delete",
            self.INDEX_DELETE_BATCH_SIZE,
        )

    def _remove_container_constraints(self, resource: ContainerDeploymentPlan) -> list[ChangedFieldResult]:
        return self._remove_container_fields(
            resource.constraints_to_remove,
            "/models/containers/constraints/delete",
            self.CONSTRAINT_DELETE_BATCH_SIZE,
        )

    def _remove_container_fields(
        self,
        fields_to_remove: Mapping[T_Reference, FieldChange],
        endpoint: str,
        batch_size: int,
    ) -> list[ChangedFieldResult]:
        if not fields_to_remove:
            return []
        results: list[ChangedFieldResult] = []
        for batch in chunker_sequence(list(fields_to_remove.keys()), batch_size):
            responses = self.client.http_client.request_with_retries(
                ItemsRequest(
                    endpoint_url=self.client.config.create_api_url(endpoint),
                    method="POST",
                    body=ItemIDBody(items=batch),
                )
            )
            results.extend(self._process_field_responses(responses, fields_to_remove))
        return results

    @classmethod
    def _process_resource_responses(
        cls, responses: APIResponse, change_by_id: dict[T_ResourceId, ResourceChange], endpoint: DataModelEndpoint
    ) -> list[ChangeResult]:
        results: list[ChangeResult] = []
        for response in responses:
            if isinstance(response, SuccessResponseItems | FailedResponseItems | FailedRequestItems):
                for id in response.ids:
                    if id not in change_by_id:
                        continue
                    results.append(ChangeResult(change=change_by_id[id], message=response, endpoint=endpoint))
            else:
                # This should never happen as we do a ItemsRequest should always return ItemMessage responses
                raise ValueError("Bug in Neat. Got an unexpected response type.")
        return results

    @classmethod
    def _process_field_responses(
        cls, responses: APIResponse, change_by_id: Mapping[T_Reference, FieldChange]
    ) -> list[ChangedFieldResult]:
        results: list[ChangedFieldResult] = []
        for response in responses:
            if isinstance(response, SuccessResponseItems | FailedResponseItems | FailedRequestItems):
                for id in response.ids:
                    if id not in change_by_id:
                        continue
                    results.append(ChangedFieldResult(field_change=change_by_id[id], message=response))
            else:
                # This should never happen as we do a ItemsRequest should always return ItemMessage responses
                raise RuntimeError("Bug in Neat. Got an unexpected response type.")
        return results
