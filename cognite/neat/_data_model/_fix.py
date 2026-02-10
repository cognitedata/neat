import hashlib
from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field

from cognite.neat._data_model.deployer.data_classes import (
    AddedField,
    ChangedField,
    FieldChange,
    PrimitiveField,
    RemovedField,
)
from cognite.neat._data_model.models.dms import (
    ContainerReference,
    DataModelReference,
    DataModelResource,
    SchemaResourceId,
    SpaceReference,
    ViewReference,
)
from cognite.neat._data_model.models.dms._schema import RequestSchema

# CDF constraint and index identifier max length is 43 characters
MAX_IDENTIFIER_LENGTH = 43
AUTO_SUFFIX = "__auto"
HASH_LENGTH = 8  # Short hash to ensure uniqueness when truncating
# When truncating: base_id + "_" + hash + suffix
# e.g., "VeryLongContainerName_a1b2c3d4__auto" (max 43 chars)
MAX_BASE_LENGTH_NO_HASH = MAX_IDENTIFIER_LENGTH - len(AUTO_SUFFIX)  # 37 characters
MAX_BASE_LENGTH_WITH_HASH = MAX_BASE_LENGTH_NO_HASH - HASH_LENGTH - 1  # 28 characters


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
    changes: tuple[FieldChange, ...] = Field(default_factory=tuple)
    message: str | None = None
    code: str


class FixApplicator:
    """Applies fix actions to a schema. Used as an activity in the store's provenance pipeline."""

    def __init__(self, request_schema: RequestSchema, fix_actions: list[FixAction]) -> None:
        self._request_schema = request_schema
        self._fix_actions = fix_actions
        self._seen_field_paths: set[str] = set()

    def apply_fixes(self) -> RequestSchema:
        """Apply fix actions to the schema and return the fixed schema.

        Note: This mutates the RequestSchema passed to the constructor.
        The caller is responsible for passing a deep copy if needed.
        """
        if not self._fix_actions:
            return self._request_schema

        fix_by_resource_id: dict[SchemaResourceId, list[FixAction]] = defaultdict(list)
        for action in self._fix_actions:
            fix_by_resource_id[action.resource_id].append(action)

        resources_list_lookup: dict[type, dict[SchemaResourceId, DataModelResource]] = {
            ViewReference: {view.as_reference(): view for view in self._request_schema.views},
            ContainerReference: {container.as_reference(): container for container in self._request_schema.containers},
            SpaceReference: {space.as_reference(): space for space in self._request_schema.spaces},
            DataModelReference: {self._request_schema.data_model.as_reference(): self._request_schema.data_model},
        }

        for resource_id, actions in fix_by_resource_id.items():
            resource_lookup = resources_list_lookup.get(type(resource_id))
            if resource_lookup is None:
                raise RuntimeError(
                    f"FixApplicator: Unsupported resource type {type(resource_id)}. This is a bug in NEAT."
                )
            resource = resource_lookup.get(resource_id)
            if resource is None:
                raise RuntimeError(f"FixApplicator: Resource {resource_id} not found in schema. This is a bug in NEAT.")

            all_changes_for_resource = [change for action in actions for change in action.changes]
            self._check_no_field_path_conflicts(all_changes_for_resource)
            self._apply_changes_to_resource(resource, all_changes_for_resource)

        return self._request_schema

    def _apply_changes_to_resource(self, resource: DataModelResource, changes: list[FieldChange]) -> None:
        """Apply field changes to the resource in place."""
        for change in changes:
            if not isinstance(change, PrimitiveField):
                raise RuntimeError(
                    f"FixApplicator: Only primitive field changes are supported, "
                    f"got {type(change).__name__}. This is a bug in NEAT."
                )
            if "." not in change.field_path:
                raise RuntimeError(
                    f"FixApplicator: Invalid field_path '{change.field_path}' "
                    "(expected 'field_name.identifier' format). This is a bug in NEAT."
                )
            field_name, identifier = change.field_path.split(".", maxsplit=1)
            field_map = getattr(resource, field_name, None)
            if field_map is None:
                field_map = {}
                setattr(resource, field_name, field_map)
            if isinstance(change, RemovedField):
                field_map.pop(identifier, None)
            elif isinstance(change, (AddedField, ChangedField)):
                field_map[identifier] = change.new_value
            if not field_map:
                setattr(resource, field_name, None)

    def _check_no_field_path_conflicts(self, changes: list[FieldChange]) -> None:
        """Raise if any changes touch a field_path already modified by a previous change."""
        for change in changes:
            if change.field_path in self._seen_field_paths:
                raise RuntimeError(
                    f"FixApplicator: Conflicting fixes — multiple changes to '{change.field_path}'. "
                    "This is a bug in NEAT."
                )
            self._seen_field_paths.add(change.field_path)


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
