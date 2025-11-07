import json
from typing import Any, cast, get_args

from cognite.neat._data_model.deployer.data_classes import DataModelEndpoint, DeploymentResult, SeverityType
from cognite.neat._session._html._render import render
from cognite.neat._store import NeatStore


class Result:
    """Class to handle deployment results in the NeatSession."""

    def __init__(self, store: NeatStore) -> None:
        self._store = store

    @property
    def _result(self) -> DeploymentResult | None:
        """Get deployment result from the last change in the store."""
        if change := self._store.provenance.last_change:
            if hasattr(change, "result") and change.result:
                return change.result
        return None

    def _initialize_stats(self, result: DeploymentResult) -> dict[str, Any]:
        """Initialize the statistics structure."""
        # Get all possible endpoints from the DataModelEndpoint type alias
        endpoints = get_args(DataModelEndpoint)

        return {
            "status": result.status,
            "is_dry_run": result.is_dry_run,
            "total_changes": 0,
            "by_endpoint": {
                endpoint: {"total": 0, "create": 0, "update": 0, "delete": 0, "unchanged": 0} for endpoint in endpoints
            },
            "by_change_type": {"create": 0, "update": 0, "delete": 0, "unchanged": 0},
            "by_severity": {
                SeverityType.BREAKING.name: 0,
                SeverityType.WARNING.name: 0,
                SeverityType.SAFE.name: 0,
            },
            "has_recovery": result.recovery is not None,
        }

    def _update_statistics(self, stats: dict[str, Any], endpoint: str, change_type: str, severity: str) -> None:
        """Update all statistics counters for a single resource change."""
        by_endpoint = cast(dict[str, dict[str, int]], stats["by_endpoint"])
        by_change_type = cast(dict[str, int], stats["by_change_type"])
        by_severity = cast(dict[str, int], stats["by_severity"])

        stats["total_changes"] = cast(int, stats["total_changes"]) + 1
        by_change_type[change_type] += 1
        by_endpoint[endpoint]["total"] += 1
        by_endpoint[endpoint][change_type] += 1
        by_severity[severity] += 1

    @property
    def _stats(self) -> dict[str, Any] | None:
        """Compute statistics about deployment result."""
        if not self._result:
            return None

        stats = self._initialize_stats(self._result)

        for plan in self._result.plan:
            for resource in plan.resources:
                self._update_statistics(
                    stats=stats,
                    endpoint=plan.endpoint,
                    change_type=resource.change_type,
                    severity=resource.severity.name,
                )

        return stats

    def _serialize_field_change(self, field_change: Any) -> dict[str, Any]:
        """Serialize a single field change."""
        return {
            "field_path": field_change.field_path,
            "severity": field_change.severity.name,
            "description": getattr(field_change, "description", "Field changed"),
        }

    def _serialize_resource_change(self, resource: Any, endpoint: str, change_id: int) -> dict[str, Any]:
        """Serialize a single resource change."""
        return {
            "id": change_id,
            "endpoint": endpoint,
            "change_type": resource.change_type,
            "severity": resource.severity.name,
            "resource_id": str(resource.resource_id),
            "changes": [self._serialize_field_change(fc) for fc in resource.changes],
        }

    @property
    def _serialized_changes(self) -> list[dict[str, Any]]:
        """Convert deployment changes to JSON-serializable format."""
        if not self._result:
            return []

        all_changes: list[dict[str, Any]] = []

        for plan in self._result.plan:
            for resource in plan.resources:
                change_data = self._serialize_resource_change(
                    resource=resource,
                    endpoint=plan.endpoint,
                    change_id=len(all_changes),
                )
                all_changes.append(change_data)

        return all_changes

    def _build_template_vars(self, stats: dict[str, Any]) -> dict[str, Any]:
        """Build template variables from statistics."""
        by_change_type = cast(dict[str, int], stats["by_change_type"])

        return {
            "CHANGES_JSON": json.dumps(self._serialized_changes),
            "STATS_JSON": json.dumps(stats),
            "status": cast(str, stats["status"]),
            "total_changes": cast(int, stats["total_changes"]),
            "created": by_change_type["create"],
            "updated": by_change_type["update"],
            "deleted": by_change_type["delete"],
            "unchanged": by_change_type["unchanged"],
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
