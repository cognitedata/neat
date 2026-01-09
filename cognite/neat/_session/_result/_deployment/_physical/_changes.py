import itertools
from typing import Any

from pydantic import BaseModel, Field

from cognite.neat._data_model.deployer.data_classes import (
    AddedField,
    AppliedChanges,
    ChangedField,
    ChangeResult,
    DeploymentResult,
    FieldChange,
    FieldChanges,
    RemovedField,
    ResourceChange,
)


class SerializedFieldChange(BaseModel):
    """Serialized field change for JSON output."""

    field_path: str
    severity: str
    description: str

    @classmethod
    def from_field_change(cls, field_change: FieldChange) -> list["SerializedFieldChange"]:
        """Serialize a field change, handling nested FieldChanges recursively.

        Args:
            field_change: The field change to serialize.

        Returns:
            List of serialized field changes (may be multiple if nested).
        """
        serialized_changes: list[SerializedFieldChange] = []

        if isinstance(field_change, FieldChanges):
            # Recursively handle nested changes
            for change in field_change.changes:
                serialized_changes.extend(cls.from_field_change(change))
        else:
            # Base case: single field change
            serialized_changes.append(cls._from_single_field_change(field_change))

        return serialized_changes

    @classmethod
    def _from_single_field_change(cls, field_change: FieldChange) -> "SerializedFieldChange":
        """Serialize a single non-nested field change.

        Args:
            field_change: The single field change to serialize.

        Returns:
            Serialized field change.
        """
        return cls(
            field_path=field_change.field_path,
            severity=field_change.severity.name,
            description=field_change.description
            if isinstance(field_change, AddedField | RemovedField | ChangedField)
            else "Field changed",
        )


class SerializedResourceChange(BaseModel):
    """Serialized resource change for JSON output."""

    id: int
    endpoint: str
    change_type: str
    severity: str
    resource_id: str
    message: str | None = None
    changes: list[SerializedFieldChange] = Field(default_factory=list)

    @classmethod
    def from_resource_change(
        cls, resource: ResourceChange, endpoint: str, change_id: int
    ) -> "SerializedResourceChange":
        """Serialize a single resource change.

        Args:
            resource: The resource change to serialize.
            endpoint: The endpoint type.
            change_id: Unique ID for this change.

        Returns:
            Serialized resource change.
        """
        changes: list[SerializedFieldChange] = []

        for change in resource.changes:
            changes.extend(SerializedFieldChange.from_field_change(change))

        return cls(
            id=change_id,
            endpoint=endpoint,
            change_type=resource.change_type,
            severity=resource.severity.name,
            resource_id=str(resource.resource_id),
            changes=changes,
            message=resource.message,
        )

    @classmethod
    def from_change_result(cls, change_id: int, response: ChangeResult) -> "SerializedResourceChange":
        """Serialize from a change result (actual deployment).

        Args:
            change_id: Unique ID for this change.
            response: The change result from deployment.

        Returns:
            Serialized resource change with deployment status.
        """
        serialized_resource_change = cls.from_resource_change(
            resource=response.change,
            endpoint=response.endpoint,
            change_id=change_id,
        )

        serialized_resource_change.message = response.message
        if not response.is_success:
            serialized_resource_change.change_type = "failed"

        return serialized_resource_change


class SerializedChanges(BaseModel):
    """Container for all serialized changes."""

    changes: list[SerializedResourceChange] = Field(default_factory=list)

    @classmethod
    def from_deployment_result(cls, result: DeploymentResult) -> "SerializedChanges":
        """Create SerializedChanges from a DeploymentResult.

        Args:
            result: The deployment result to serialize changes from.

        Returns:
            SerializedChanges instance with all changes.
        """
        serialized = cls()

        if not result.responses:
            serialized._add_from_dry_run(result)
        else:
            serialized._add_from_applied_changes(result.responses)

        return serialized

    def _add_from_dry_run(self, result: DeploymentResult) -> None:
        """Add changes from dry run deployment.

        Args:
            result: The deployment result in dry run mode.
        """
        # Iterate over each endpoint plan
        for endpoint_plan in result.plan:
            # Then per resource in the endpoint
            for resource in endpoint_plan.resources:
                # Then serialize individual resource change
                serialized_resource_change = SerializedResourceChange.from_resource_change(
                    resource=resource,
                    endpoint=endpoint_plan.endpoint,
                    change_id=len(self.changes),
                )
                self.changes.append(serialized_resource_change)

    def _add_from_applied_changes(self, applied_changes: AppliedChanges) -> None:
        """Add changes from actual deployment.
        Args:
            result: The deployment result from actual deployment.
        """
        for response in itertools.chain(
            applied_changes.created,
            applied_changes.merged_updated,
            applied_changes.deletions,
            applied_changes.unchanged,
            applied_changes.skipped,
        ):
            self.changes.append(SerializedResourceChange.from_change_result(len(self.changes), response))

    def model_dump_json_flat(self, **kwargs: Any) -> str:
        """Dump changes as JSON array without the wrapper key.
        Returns:
            JSON string of the changes array.
        """
        if not self.changes:
            return "[]"

        iterator = (change.model_dump_json(**kwargs) for change in self.changes)
        return f"[{','.join(iterator)}]"
