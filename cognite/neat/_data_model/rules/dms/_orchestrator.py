from collections import defaultdict
from collections.abc import Callable

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._fix import FixAction
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms import (
    ContainerReference,
    DataModelReference,
    SchemaResourceId,
    SpaceReference,
    ViewReference,
)
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._data_model.rules.dms._base import DataModelRule
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.useful_types import ModusOperandi


def _snapshot_key_for_resource(resource_id: SchemaResourceId) -> str:
    """Map a resource reference to its SchemaSnapshot field name."""
    if isinstance(resource_id, SpaceReference):
        return "spaces"
    elif isinstance(resource_id, DataModelReference):
        return "data_model"
    elif isinstance(resource_id, ViewReference):
        return "views"
    elif isinstance(resource_id, ContainerReference):
        return "containers"
    raise ValueError(f"Unsupported resource type: {type(resource_id)}")


class DmsDataModelRulesOrchestrator(OnSuccessIssuesChecker):
    """DMS Data Model rules orchestrator, used to execute DMS data model rules on a single data model represented
    as RequestSchema."""

    def __init__(
        self,
        cdf_snapshot: SchemaSnapshot,
        limits: SchemaLimits,
        modus_operandi: ModusOperandi = "additive",
        can_run_validator: Callable[[str, type], bool] | None = None,
        enable_alpha_validators: bool = False,
        apply_fixes: bool = False,
    ) -> None:
        super().__init__()
        self._cdf_snapshot = cdf_snapshot
        self._limits = limits
        self._modus_operandi = modus_operandi
        self._can_run_validator = can_run_validator or (lambda code, issue_type: True)  # type: ignore
        self._has_run = False
        self._enable_alpha_validators = enable_alpha_validators
        self._apply_fixes = apply_fixes

    def run(self, request_schema: RequestSchema) -> SchemaSnapshot | None:
        """Run quality assessment on the DMS data model.

        Returns:
            The fixed snapshot if fixes were applied, None otherwise.
        """
        fixed_snapshot: SchemaSnapshot | None = None
        if self._apply_fixes:
            validation_resources = self._gather_validation_resources(request_schema)
            fix_by_resource_id = self._collect_fix_actions(validation_resources)

            fix_snapshot = SchemaSnapshot.from_request_schema(request_schema, deep_copy=False)

            # Build update dicts per resource type, starting from the full snapshot dicts
            # so model_copy doesn't discard unmodified resources.
            snapshot_update: dict[str, dict] = {}
            for resource_id, actions in fix_by_resource_id.items():
                self._check_no_field_path_conflicts(actions)

                resource_key = _snapshot_key_for_resource(resource_id)
                if resource_key not in snapshot_update:
                    snapshot_update[resource_key] = dict(getattr(fix_snapshot, resource_key))

                current_resource = snapshot_update[resource_key].get(resource_id)
                if current_resource is None:
                    raise ValueError(f"Resource {resource_id} not found in snapshot")
                for action in actions:
                    current_resource = action.as_resource_update(current_resource)
                snapshot_update[resource_key][resource_id] = current_resource

            fixed_snapshot = fix_snapshot.model_copy(update=snapshot_update)

        validation_resources = self._gather_validation_resources(request_schema)

        # Initialize all validators
        validators: list[DataModelRule] = [
            validator(validation_resources) for validator in get_concrete_subclasses(DataModelRule)
        ]

        # Run validators
        for validator in validators:
            if validator.alpha and not self._enable_alpha_validators:
                continue
            if self._can_run_validator(validator.code, validator.issue_type):
                self._issues.extend(validator.validate())

        self._has_run = True
        return fixed_snapshot

    def _gather_validation_resources(self, request_schema: RequestSchema) -> ValidationResources:
        # Deep copy for validation - we don't want to modify the original during merge/analysis
        local = SchemaSnapshot.from_request_schema(request_schema, deep_copy=True)

        return ValidationResources(
            cdf=self._cdf_snapshot,
            local=local,
            limits=self._limits,
            modus_operandi=self._modus_operandi,
        )

    def _collect_fix_actions(
        self, validation_resources: ValidationResources
    ) -> dict[SchemaResourceId, list[FixAction]]:
        """Collect fix actions from all fixable validators, grouped by resource ID."""
        fix_by_resource_id: dict[SchemaResourceId, list[FixAction]] = defaultdict(list)
        validators: list[DataModelRule] = [
            validator(validation_resources) for validator in get_concrete_subclasses(DataModelRule)
        ]

        for validator in validators:
            if not validator.fixable:
                continue
            if validator.alpha and not self._enable_alpha_validators:
                continue
            if self._can_run_validator(validator.code, validator.issue_type):
                for action in validator.fix():
                    fix_by_resource_id[action.resource_id].append(action)

        return fix_by_resource_id

    @staticmethod
    def _check_no_field_path_conflicts(actions: list[FixAction]) -> None:
        """Raise if multiple actions touch the same field_path on the same resource."""
        seen_paths: set[str] = set()
        for action in actions:
            for change in action.changes:
                if change.field_path in seen_paths:
                    raise ValueError(f"Conflicting fixes: multiple changes to '{change.field_path}'")
                seen_paths.add(change.field_path)
