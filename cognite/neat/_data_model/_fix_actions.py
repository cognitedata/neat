"""Fix actions for auto-fixing data model issues."""

from typing import Any

from cognite.neat._data_model.deployer.data_classes import (
    AddedField,
    FieldChange,
    RemovedField,
    ResourceChange,
)
from cognite.neat._data_model.models.dms import ContainerReference, T_DataModelResource, T_ResourceId
from cognite.neat._data_model.models.dms._schema import RequestSchema


class FixAction(ResourceChange[T_ResourceId, T_DataModelResource]):
    """An atomic, individually-applicable fix for a schema issue.

    FixAction extends ResourceChange to represent a change that can be applied to a RequestSchema
    to fix an issue identified by a validator. This provides consistency with the deployment
    diff system - fixes use the same data structures as deployment changes.

    Attributes:
        resource_id: Reference to the resource being modified (e.g., ContainerReference).
        changes: List of field-level changes (AddedField, RemovedField).
        message: Human-readable description of what this fix does.
        code: The validator code (e.g., "NEAT-DMS-PERFORMANCE-001") for grouping in UI.
    """

    code: str

    def __call__(self, schema: RequestSchema) -> None:
        """Apply this fix to the schema in-place."""
        resource = self._get_resource(schema)
        for change in self.changes:
            self._apply_field_change(resource, change)

    def _get_resource(self, schema: RequestSchema) -> Any:
        """Get the resource from the schema based on resource_id type."""
        if isinstance(self.resource_id, ContainerReference):
            for container in schema.containers:
                if container.as_reference() == self.resource_id:
                    return container
            raise ValueError(f"Container {self.resource_id} not found in schema")
        # Add more resource types as needed (ViewReference, etc.)
        raise ValueError(f"Unsupported resource type: {type(self.resource_id)}")

    def _apply_field_change(self, resource: Any, change: FieldChange) -> None:
        """Apply a single field change to a resource."""
        parts = change.field_path.split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid field_path: {change.field_path}")

        field_type, identifier = parts
        collection = getattr(resource, field_type, None)

        if isinstance(change, AddedField):
            if collection is None:
                collection = {}
                setattr(resource, field_type, collection)
            collection[identifier] = change.new_value
        elif isinstance(change, RemovedField):
            if collection is not None and identifier in collection:
                del collection[identifier]
                # Clean up empty collections
                if not collection:
                    setattr(resource, field_type, None)

    @property
    def fix_id(self) -> str:
        """Generate a unique ID from resource_id and field paths for sorting/deduplication."""
        field_paths = ",".join(sorted(c.field_path for c in self.changes))
        return f"{self.code}:{self.resource_id!s}:{field_paths}"
