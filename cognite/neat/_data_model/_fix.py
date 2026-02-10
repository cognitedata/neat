import hashlib
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from cognite.neat._data_model.deployer.data_classes import (
    AddedField,
    ChangedField,
    FieldChange,
    PrimitiveField,
    RemovedField,
)
from cognite.neat._data_model.models.dms import (
    DataModelResource,
    SchemaResourceId,
)
from cognite.neat._data_model.models.dms._references import ContainerReference

# CDF constraint and index identifier max length is 43 characters
MAX_IDENTIFIER_LENGTH = 43
AUTO_SUFFIX = "__auto"
HASH_LENGTH = 8  # Short hash to ensure uniqueness when truncating
# When truncating: base_id + "_" + hash + suffix
# e.g., "VeryLongContainerName_a1b2c3d4__auto" (max 43 chars)
MAX_BASE_LENGTH_NO_HASH = MAX_IDENTIFIER_LENGTH - len(AUTO_SUFFIX)  # 37 characters
MAX_BASE_LENGTH_WITH_HASH = MAX_BASE_LENGTH_NO_HASH - HASH_LENGTH - 1  # 28 characters


def make_auto_id(base_id: str) -> str:
    """Generate an auto-generated identifier with truncation if needed.

    CDF has a 43-character limit on constraint/index identifiers. This function
    ensures the ID stays within that limit while maintaining uniqueness.

    Args:
        base_id: The primary identifier to use (e.g., external_id or property_id).

    Returns:
        For short base_ids (≤37 chars): "{base_id}__auto"
        For long base_ids (>37 chars): "{truncated_id}_{hash}__auto"
    """
    if len(base_id) <= MAX_BASE_LENGTH_NO_HASH:
        return f"{base_id}{AUTO_SUFFIX}"

    hash_suffix = hashlib.sha256(base_id.encode()).hexdigest()[:HASH_LENGTH]
    truncated_id = base_id[:MAX_BASE_LENGTH_WITH_HASH]
    return f"{truncated_id}_{hash_suffix}{AUTO_SUFFIX}"


def make_auto_constraint_id(dst: ContainerReference) -> str:
    """Generate a constraint identifier for auto-generated requires constraints."""
    return make_auto_id(dst.external_id)


def make_auto_index_id(property_id: str) -> str:
    """Generate an index identifier for auto-generated indexes."""
    return make_auto_id(property_id)


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

    def as_resource_update(self, current_resource: DataModelResource) -> DataModelResource:
        """Apply this action's changes to the resource, returning an updated copy via model_copy."""
        resource_update: dict[str, Any] = {}
        for change in self.changes:
            if not isinstance(change, PrimitiveField):
                raise ValueError(f"Only primitive field changes are supported, got {type(change).__name__}")
            if "." not in change.field_path:
                raise ValueError(f"Invalid field_path (expected 'collection.identifier' format): {change.field_path}")
            top_level, identifier = change.field_path.split(".", maxsplit=1)

            if top_level not in resource_update:
                existing = getattr(current_resource, top_level, None)
                resource_update[top_level] = dict(existing) if existing else {}

            if isinstance(change, RemovedField):
                resource_update[top_level].pop(identifier, None)
            elif isinstance(change, (AddedField, ChangedField)):
                resource_update[top_level][identifier] = change.new_value

        for key in resource_update:
            if not resource_update[key]:
                resource_update[key] = None

        return current_resource.model_copy(update=resource_update)
