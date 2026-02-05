from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.deployer.data_classes import (
    AddedField,
    ChangedField,
    FieldChange,
    RemovedField,
)
from cognite.neat._data_model.models.dms import (
    ContainerReference,
    DataModelReference,
    SchemaResourceId,
    SpaceReference,
    ViewReference,
)


class FixAction(BaseModel):
    """An atomic, individually-applicable fix for a schema issue.

    Attributes:
        resource_id: Reference to the resource being modified.
        changes: List of field-level changes.
        message: Human-readable description of what this fix does.
        code: The validator code (e.g., "NEAT-DMS-PERFORMANCE-001") for grouping in UI.
    """

    model_config = ConfigDict(frozen=True)

    resource_id: SchemaResourceId
    changes: list[FieldChange] = Field(default_factory=list)
    message: str | None = None
    code: str

    def __call__(self, snapshot: SchemaSnapshot) -> None:
        """Apply this fix to the snapshot in-place.

        Args:
            snapshot: A SchemaSnapshot to apply fixes to. Use SchemaSnapshot.from_request_schema()
                     with deep_copy=False to create a thin snapshot that references the original
                     RequestSchema objects, so mutations flow through.
        """
        resource = self._get_resource(snapshot)
        for change in self.changes:
            self._apply_field_change(resource, change)

    def _get_resource(self, snapshot: SchemaSnapshot) -> Any:
        """Get the resource from the snapshot based on resource_id type (O(1) lookup)."""
        if isinstance(self.resource_id, SpaceReference):
            resource = snapshot.spaces.get(self.resource_id)
        elif isinstance(self.resource_id, DataModelReference):
            resource = snapshot.data_model.get(self.resource_id)
        elif isinstance(self.resource_id, ViewReference):
            resource = snapshot.views.get(self.resource_id)
        elif isinstance(self.resource_id, ContainerReference):
            resource = snapshot.containers.get(self.resource_id)
        else:
            raise ValueError(f"Unsupported resource type: {type(self.resource_id)}")

        if resource is None:
            raise ValueError(f"Resource {self.resource_id} not found in snapshot")
        return resource

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
        elif isinstance(change, ChangedField):
            if collection is None:
                raise ValueError(f"Cannot change field {change.field_path}: collection does not exist")
            if identifier not in collection:
                raise ValueError(f"Cannot change field {change.field_path}: identifier not found")
            collection[identifier] = change.new_value
        elif isinstance(change, RemovedField):
            if collection is not None and identifier in collection:
                del collection[identifier]
                # Clean up empty collections
                if not collection:
                    setattr(resource, field_type, None)
        else:
            raise ValueError(f"Unsupported field change type: {type(change)}")
