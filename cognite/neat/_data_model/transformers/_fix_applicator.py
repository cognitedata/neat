from collections import defaultdict

from cognite.neat._data_model._fix import FixAction
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
from cognite.neat._data_model.transformers._base import Transformer


class FixApplicator(Transformer):
    """Applies the changes in FixAction objects to a schema."""

    def __init__(self, request_schema: RequestSchema, fix_actions: list[FixAction]) -> None:
        self._request_schema = request_schema.model_copy(deep=True)
        self._fix_actions = fix_actions

    def transform(self) -> RequestSchema:
        """Apply fix actions and return the fixed schema (a deep copy of the original)."""
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
                    f"{type(self).__name__}: Unsupported resource type {type(resource_id)}. This is a bug in NEAT."
                )
            resource = resource_lookup.get(resource_id)
            if resource is None:
                raise RuntimeError(
                    f"{type(self).__name__}: Resource {resource_id} not found in schema. This is a bug in NEAT."
                )

            all_changes_for_resource = [change for action in actions for change in action.changes]
            self._check_no_field_path_conflicts(all_changes_for_resource)
            self._apply_changes_to_resource(resource, all_changes_for_resource)

        return self._request_schema

    def _apply_changes_to_resource(self, resource: DataModelResource, changes: list[FieldChange]) -> None:
        """Apply field changes to the resource in place."""
        for change in changes:
            if not isinstance(change, PrimitiveField):
                raise RuntimeError(
                    f"{type(self).__name__}: Only primitive field changes are supported, "
                    f"got {type(change).__name__}. This is a bug in NEAT."
                )
            if "." not in change.field_path:
                raise RuntimeError(
                    f"{type(self).__name__}: Invalid field_path '{change.field_path}' "
                    "(expected 'field_name.identifier' format). This is a bug in NEAT."
                )
            field_name, identifier = change.field_path.split(".", maxsplit=1)
            field_map = getattr(resource, field_name, None)
            if field_map is None:
                field_map = {}
                setattr(resource, field_name, field_map)
            if isinstance(change, RemovedField):
                field_map.pop(identifier, None)
            elif isinstance(change, AddedField | ChangedField):
                field_map[identifier] = change.new_value
            if not field_map:
                setattr(resource, field_name, None)

    def _check_no_field_path_conflicts(self, changes: list[FieldChange]) -> None:
        """Raise if any changes touch a field_path already modified by a previous change."""
        seen_paths: set[str] = set()
        for change in changes:
            if change.field_path in seen_paths:
                raise RuntimeError(
                    f"{type(self).__name__}: Conflicting fixes — multiple changes "
                    f"to '{change.field_path}'. This is a bug in NEAT."
                )
            seen_paths.add(change.field_path)
