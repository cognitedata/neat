import itertools
from typing import Any, Literal, cast, get_args

from pydantic import BaseModel, Field

from cognite.neat._data_model.deployer.data_classes import (
    AppliedChanges,
    DataModelEndpoint,
    DeploymentResult,
)


class EndpointStatistics(BaseModel):
    """Statistics for a single endpoint."""

    create: int = 0
    update: int = 0
    delete: int = 0
    skip: int = 0
    unchanged: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        """Total number of changes for this endpoint."""
        return self.create + self.update + self.delete + self.skip + self.unchanged + self.failed

    def increment(self, change_type: Literal["create", "update", "delete", "unchanged", "skip", "failed"]) -> None:
        """Increment the count for a specific change type.

        Args:
            change_type: The type of change (create, update, delete, skip, unchanged, failed).
        """
        if hasattr(self, change_type):
            setattr(self, change_type, getattr(self, change_type) + 1)
        else:
            raise RuntimeError(f"Unknown change type: {change_type}. This is a bug in NEAT.")


class ChangeTypeStatistics(BaseModel):
    """Statistics grouped by change type."""

    create: int = 0
    update: int = 0
    delete: int = 0
    skip: int = 0
    unchanged: int = 0
    failed: int = 0

    def increment(self, change_type: Literal["create", "update", "delete", "unchanged", "skip", "failed"]) -> None:
        """Increment the count for a specific change type.

        Args:
            change_type: The type of change (create, update, delete, skip, unchanged, failed).
        """
        if hasattr(self, change_type):
            setattr(self, change_type, getattr(self, change_type) + 1)
        else:
            raise RuntimeError(f"Unknown change type: {change_type}. This is a bug in NEAT.")


class SeverityStatistics(BaseModel):
    """Statistics grouped by severity."""

    SAFE: int = 0
    WARNING: int = 0
    BREAKING: int = 0

    def increment(self, severity: Literal["SAFE", "WARNING", "BREAKING"]) -> None:
        """Increment the count for a specific severity level.

        Args:
            severity: The severity level (SAFE, WARNING, BREAKING).
        """
        if hasattr(self, severity):
            setattr(self, severity, getattr(self, severity) + 1)
        else:
            raise RuntimeError(f"Unknown severity level: {severity}. This is a bug in NEAT.")


class DeploymentStatistics(BaseModel):
    """Overall deployment statistics."""

    by_endpoint: dict[str, EndpointStatistics] = Field(default_factory=dict)
    by_change_type: ChangeTypeStatistics = Field(default_factory=ChangeTypeStatistics)
    by_severity: SeverityStatistics = Field(default_factory=SeverityStatistics)

    @property
    def total_changes(self) -> int:
        """Total number of changes in the deployment."""
        return sum(endpoint_stats.total for endpoint_stats in self.by_endpoint.values())

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Include computed properties in serialization."""
        data = super().model_dump(**kwargs)
        data["total_changes"] = self.total_changes
        return data

    @classmethod
    def from_deployment_result(cls, result: DeploymentResult) -> "DeploymentStatistics":
        """Create DeploymentStatistics from a DeploymentResult.

        Args:
            result: The deployment result to create statistics from.

        Returns:
            DeploymentStatistics instance with computed statistics.
        """
        stats = cls(
            by_endpoint={endpoint: EndpointStatistics() for endpoint in get_args(DataModelEndpoint)},
            by_change_type=ChangeTypeStatistics(),
            by_severity=SeverityStatistics(),
        )

        if result.is_dry_run:
            stats._update_from_dry_run(result)
        else:
            stats._update_from_deployment(result)

        return stats

    def _update_from_dry_run(self, result: DeploymentResult) -> None:
        """Update statistics from dry run mode.

        Args:
            result: The deployment result in dry run mode.
        """
        for plan in result.plan:
            for resource in plan.resources:
                self._update_single_stat(
                    endpoint=plan.endpoint,
                    change_type=resource.change_type,
                    severity=cast(Literal["SAFE", "WARNING", "BREAKING"], resource.severity.name),
                )

    def _update_from_deployment(self, result: DeploymentResult) -> None:
        """Update statistics from actual deployment mode.

        Args:
            result: The deployment result from actual deployment.
        """
        applied_changes = cast(AppliedChanges, result.responses)

        for response in itertools.chain(
            applied_changes.created,
            applied_changes.merged_updated,
            applied_changes.deletions,
            applied_changes.unchanged,
            applied_changes.skipped,
        ):
            self._update_single_stat(
                endpoint=response.endpoint,
                change_type=response.change.change_type if response.is_success else "failed",
                severity=cast(Literal["SAFE", "WARNING", "BREAKING"], response.change.severity.name),
            )

    def _update_single_stat(
        self,
        endpoint: str,
        change_type: Literal["create", "update", "delete", "unchanged", "skip", "failed"],
        severity: Literal["SAFE", "WARNING", "BREAKING"],
    ) -> None:
        """Update all statistics for a single change.

        Args:
            endpoint: The endpoint type (spaces, containers, views, datamodels).
            change_type: The type of change (create, update, delete, skip, unchanged, failed).
            severity: The severity level (SAFE, WARNING, BREAKING).
        """
        # Update by change type statistics
        self.by_change_type.increment(change_type)

        # Update by endpoint statistics
        if endpoint in self.by_endpoint:
            self.by_endpoint[endpoint].increment(change_type)
        else:
            raise RuntimeError(f"Unknown endpoint: {endpoint}. This is a bug in NEAT.")

        # Update severity statistics
        self.by_severity.increment(severity)
