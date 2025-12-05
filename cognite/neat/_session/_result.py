import json
import uuid
from typing import Any, cast, get_args

from pydantic import BaseModel, Field

from cognite.neat._data_model.deployer.data_classes import (
    AddedField,
    AppliedChanges,
    ChangeResult,
    ChangedField,
    DataModelEndpoint,
    DeploymentResult,
    FieldChange,
    FieldChanges,
    HTTPChangeResult,
    MultiHTTPChangeResult,
    NoOpChangeResult,
    RemovedField,
    ResourceChange,
    resource_id_to_endpoint,
)
from cognite.neat._session._html._render import render
from cognite.neat._store import NeatStore
from cognite.neat._utils.http_client._data_classes import SuccessResponseItems


class EndpointStatistics(BaseModel):
    """Statistics for a single endpoint."""

    total: int = 0
    create: int = 0
    update: int = 0
    delete: int = 0
    skip: int = 0
    unchanged: int = 0
    failed: int = 0


class ChangeTypeStatistics(BaseModel):
    """Statistics grouped by change type."""

    create: int = 0
    update: int = 0
    delete: int = 0
    skip: int = 0
    unchanged: int = 0
    failed: int = 0


class SeverityStatistics(BaseModel):
    """Statistics grouped by severity."""

    SAFE: int = 0
    WARNING: int = 0
    BREAKING: int = 0


class DeploymentStatistics(BaseModel):
    """Overall deployment statistics."""

    status: str
    is_dry_run: bool
    total_changes: int = 0
    by_endpoint: dict[str, EndpointStatistics] = Field(default_factory=dict)
    by_change_type: ChangeTypeStatistics = Field(default_factory=ChangeTypeStatistics)
    by_severity: SeverityStatistics = Field(default_factory=SeverityStatistics)
    has_recovery: bool = False


class SerializedFieldChange(BaseModel):
    """Serialized field change for JSON output."""

    field_path: str
    severity: str
    description: str


class SerializedResourceChange(BaseModel):
    """Serialized resource change for JSON output."""

    id: int
    endpoint: str
    change_type: str
    severity: str
    resource_id: str
    message: str | None = None
    changes: list[SerializedFieldChange] = Field(default_factory=list)


class Result:
    """Class to handle deployment results in the NeatSession."""

    def __init__(self, store: NeatStore) -> None:
        self._store = store

    @property
    def _result(self) -> DeploymentResult | None:
        """Get deployment result from the last change in the store."""
        if change := self._store.provenance.last_change:
            if change.result:
                return change.result
        return None

    @staticmethod
    def _initialize_stats(result: DeploymentResult) -> DeploymentStatistics:
        """Initialize the statistics structure."""
        # Get all possible endpoints from the DataModelEndpoint type alias
        endpoints = get_args(DataModelEndpoint)

        return DeploymentStatistics(
            status=result.status,
            is_dry_run=result.is_dry_run,
            total_changes=0,
            by_endpoint={endpoint: EndpointStatistics() for endpoint in endpoints},
            by_change_type=ChangeTypeStatistics(),
            by_severity=SeverityStatistics(),
            has_recovery=result.recovery is not None,
        )

    @staticmethod
    def _update_statistics(stats: DeploymentStatistics, endpoint: str, change_type: str, severity: str) -> None:
        """Update all statistics counters for a single resource change."""
        stats.total_changes += 1

        # Update change type statistics
        setattr(stats.by_change_type, change_type, getattr(stats.by_change_type, change_type) + 1)

        # Update endpoint statistics
        endpoint_stats = stats.by_endpoint[endpoint]
        endpoint_stats.total += 1
        setattr(endpoint_stats, change_type, getattr(endpoint_stats, change_type) + 1)

        # Update severity statistics
        setattr(stats.by_severity, severity, getattr(stats.by_severity, severity) + 1)


    def _update_dry_run_statistics(self, stats: DeploymentStatistics) -> None:
        """Update statistics specific to dry run mode."""

        for plan in self._result.plan:
            for resource in plan.resources:
                self._update_statistics(
                    stats=stats,
                    endpoint=plan.endpoint,
                    change_type=resource.change_type,
                    severity=resource.severity.name,
                )

    def _update_deployment_statistics(self, stats: DeploymentStatistics) -> None:
        """Update statistics specific to actual deployment mode."""

        applied_changes = cast(AppliedChanges, self._result.responses)


        # create
        for response in applied_changes.created:
                self._update_statistics(
                    stats=stats,
                    endpoint=response.endpoint,
                    change_type=response.change.change_type if response.is_success else "failed",
                    severity=response.change.severity.name,
                )
        # update
        for response in applied_changes.merged_updated:
                self._update_statistics(
                    stats=stats,
                    endpoint=response.endpoint,
                    change_type=response.change.change_type if response.is_success else "failed",
                    severity=response.change.severity.name,
                )

        # delete
        for response in applied_changes.deletions:
                self._update_statistics(
                    stats=stats,
                    endpoint=response.endpoint,
                    change_type=response.change.change_type if response.is_success else "failed",
                    severity=response.change.severity.name,
                )

        # unchanged
        for response in applied_changes.unchanged:
                self._update_statistics(
                    stats=stats,
                    endpoint=response.endpoint,
                    change_type=response.change.change_type if response.is_success else "failed",
                    severity=response.change.severity.name,
                )

        # skipped
        for response in applied_changes.skipped:
                self._update_statistics(
                    stats=stats,
                    endpoint=response.endpoint,
                    change_type=response.change.change_type if response.is_success else "failed",
                    severity=response.change.severity.name,
                )

    @property
    def _stats(self) -> DeploymentStatistics | None:
        """Compute statistics about deployment result."""
        if not self._result:
            return None

        stats = self._initialize_stats(self._result)

        if self._result.is_dry_run:
             self._update_dry_run_statistics(stats)
        else:
             self._update_deployment_statistics(stats)

        return stats

    def _serialize_single_field_change(self, field_change: FieldChange) -> SerializedFieldChange:
        """Serialize a single non-nested field change."""
        return SerializedFieldChange(
            field_path=field_change.field_path,
            severity=field_change.severity.name,
            description=field_change.description
            if isinstance(field_change, AddedField | RemovedField | ChangedField)
            else "Field changed",
        )

    def _serialize_field_change(self, field_change: FieldChange) -> list[SerializedFieldChange]:
        """Serialize a field change, handling nested FieldChanges recursively."""
        serialized_changes: list[SerializedFieldChange] = []

        if isinstance(field_change, FieldChanges):
            # Recursively handle nested changes
            for change in field_change.changes:
                serialized_changes.extend(self._serialize_field_change(change))
        else:
            # Base case: single field change
            serialized_changes.append(self._serialize_single_field_change(field_change))

        return serialized_changes

    def _serialize_resource_change(
        self, resource: ResourceChange, endpoint: str, change_id: int
    ) -> SerializedResourceChange:
        """Serialize a single resource change."""
        changes: list[SerializedFieldChange] = []

        for change in resource.changes:
            changes.extend(self._serialize_field_change(change))

        return SerializedResourceChange(
            id=change_id,
            endpoint=endpoint,
            change_type=resource.change_type,
            severity=resource.severity.name,
            resource_id=str(resource.resource_id),
            changes=changes,
        )


    def _serialize_dry_run_changes(self) -> list[SerializedResourceChange]:
        """Serialize changes from dry run deployment."""
        all_changes: list[SerializedResourceChange] = []

        # iterate over each endpoint plan
        for endpoint_plan in self._result.plan:
            # then per resource in the endpoint
            for resource in endpoint_plan.resources:

                # then serialize individual resource change
                serialized_resource_change = self._serialize_resource_change(
                    resource=resource,
                    endpoint=endpoint_plan.endpoint,
                    change_id=len(all_changes),
                )
                all_changes.append(serialized_resource_change)

        return all_changes


    def _serialize_apply_change_result(self, change_id: int, response: ChangeResult)-> SerializedResourceChange:


        serialized_resource_change = self._serialize_resource_change(
            resource=response.change,
            endpoint=response.endpoint,
            change_id=change_id,
        )

        serialized_resource_change.message = response.message
        if not response.is_success:
            serialized_resource_change.change_type = "failed"

        return serialized_resource_change


    def _serialize_deployment_changes(self) -> list[SerializedResourceChange]:
        """Serialize changes from actual deployment."""
        all_changes: list[SerializedResourceChange] = []

        # ACTUAL DEPLOYMENT MODE
        applied_changes = cast(AppliedChanges, self._result.responses)

        for response in applied_changes.created:
            all_changes.append(self._serialize_apply_change_result(len(all_changes), response))

        for response in applied_changes.merged_updated:
            all_changes.append(self._serialize_apply_change_result(len(all_changes), response))

        for response in applied_changes.deletions:
            all_changes.append(self._serialize_apply_change_result(len(all_changes), response))

        for response in applied_changes.unchanged:
            all_changes.append(self._serialize_apply_change_result(len(all_changes), response))

        for response in applied_changes.skipped:
            all_changes.append(self._serialize_apply_change_result(len(all_changes), response))
        return all_changes

    @property
    def _serialized_changes(self) -> list[SerializedResourceChange]:
        """Convert deployment changes to JSON-serializable format."""
        if not self._result:
            return []


        return self._serialize_dry_run_changes() if self._result.is_dry_run else self._serialize_deployment_changes()


    def _build_template_vars(self, stats: DeploymentStatistics) -> dict[str, Any]:
        """Build template variables from statistics."""
        # Generate unique ID for this render to avoid conflicts in Jupyter
        unique_id = uuid.uuid4().hex[:8]

        # Convert Pydantic models to dicts for JSON serialization
        serialized_changes = [change.model_dump() for change in self._serialized_changes]

        return {
            "CHANGES_JSON": json.dumps(serialized_changes),
            "STATS_JSON": stats.model_dump_json(),
            "status": stats.status,
            "total_changes": stats.total_changes,
            "created": stats.by_change_type.create,
            "updated": stats.by_change_type.update,
            "deleted": stats.by_change_type.delete,
            "skipped": stats.by_change_type.skip,
            "unchanged": stats.by_change_type.unchanged,
            "unique_id": unique_id,
        }

    def _repr_html_(self) -> str:
        """Generate interactive HTML representation."""
        if not self._result:
            return "<p>No deployment result available</p>"

        stats = self._stats
        if not stats:
            return "<p>Unable to compute deployment statistics</p>"

        template_vars = self._build_template_vars(stats)
        return render("deployment", template_vars)
