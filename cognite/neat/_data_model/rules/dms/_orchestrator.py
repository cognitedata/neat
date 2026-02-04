from collections.abc import Callable
from datetime import datetime, timezone

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._fix_actions import FixAction
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._data_model.rules.dms._base import DataModelRule
from cognite.neat._issues import Issue
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.useful_types import ModusOperandi


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
    ) -> None:
        super().__init__()
        self._cdf_snapshot = cdf_snapshot
        self._limits = limits
        self._modus_operandi = modus_operandi
        self._can_run_validator = can_run_validator or (lambda code, issue_type: True)  # type: ignore
        self._has_run = False
        self._enable_alpha_validators = enable_alpha_validators

    def run(self, request_schema: RequestSchema) -> None:
        """Run quality assessment on the DMS data model."""

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

    def _gather_validation_resources(self, request_schema: RequestSchema) -> ValidationResources:
        # we do not want to modify the original request schema during validation
        copy = request_schema.model_copy(deep=True)
        local = SchemaSnapshot(
            data_model={request_schema.data_model.as_reference(): copy.data_model},
            views={view.as_reference(): view for view in copy.views},
            containers={container.as_reference(): container for container in copy.containers},
            spaces={space.as_reference(): space for space in copy.spaces},
            node_types={node_type: node_type for node_type in copy.node_types},
            timestamp=datetime.now(timezone.utc),
        )

        return ValidationResources(
            cdf=self._cdf_snapshot,
            local=local,
            limits=self._limits,
            modus_operandi=self._modus_operandi,
        )


class DmsDataModelFixer(OnSuccessIssuesChecker):
    """Validates and optionally fixes a DMS data model.

    This class extends the validation functionality to also apply automatic fixes
    for issues identified by fixable validators. Fixes are applied in priority order
    (lower priority values first), then re-validated to report remaining issues.

    Attributes:
        apply_fixes: Whether to apply available fixes to the schema.
    """

    def __init__(
        self,
        cdf_snapshot: SchemaSnapshot,
        limits: SchemaLimits,
        modus_operandi: ModusOperandi = "additive",
        can_run_validator: Callable[[str, type], bool] | None = None,
        enable_alpha_validators: bool = False,
        apply_fixes: bool = True,
    ) -> None:
        super().__init__()
        self._cdf_snapshot = cdf_snapshot
        self._limits = limits
        self._modus_operandi = modus_operandi
        self._can_run_validator = can_run_validator or (lambda code, issue_type: True)  # type: ignore
        self._has_run = False
        self._enable_alpha_validators = enable_alpha_validators
        self._apply_fixes = apply_fixes

    def run(self, request_schema: RequestSchema) -> None:
        """Run validation and optionally apply fixes to the DMS data model.

        If apply_fixes is True:
        1. Collect fix actions from fixable validators
        2. Deduplicate fix actions
        3. Apply fixes to the schema (in-place modification)
        4. Re-run validation to report remaining issues

        Args:
            request_schema: The schema to validate and optionally fix.
                Note: If apply_fixes is True, this schema will be modified in-place.
        """
        if self._apply_fixes:
            # Collect fix actions from fixable validators
            validation_resources = self._gather_validation_resources(request_schema)
            all_actions = self._collect_fix_actions(validation_resources)
            unique_actions = self._deduplicate_actions(all_actions)

            # Apply fixes to the original schema (not the copy)
            for action in unique_actions:
                action(request_schema)
                self._applied_fixes.append(action)

            # Re-validate to get remaining issues
            validation_resources = self._gather_validation_resources(request_schema)
            self._issues.extend(self._run_validators(validation_resources))
        else:
            # No fixes, just validate
            validation_resources = self._gather_validation_resources(request_schema)
            self._issues.extend(self._run_validators(validation_resources))

        self._has_run = True

    def _collect_fix_actions(self, validation_resources: ValidationResources) -> list[FixAction]:
        """Collect fix actions from all fixable validators."""
        actions: list[FixAction] = []
        validators: list[DataModelRule] = [
            validator(validation_resources) for validator in get_concrete_subclasses(DataModelRule)
        ]

        for validator in validators:
            if not validator.fixable:
                continue
            if validator.alpha and not self._enable_alpha_validators:
                continue
            if self._can_run_validator(validator.code, validator.issue_type):
                actions.extend(validator.fix())

        return actions

    def _run_validators(self, validation_resources: ValidationResources) -> list[Issue]:
        """Run all validators and return the issues found."""
        issues: list[Issue] = []
        validators: list[DataModelRule] = [
            validator(validation_resources) for validator in get_concrete_subclasses(DataModelRule)
        ]

        for validator in validators:
            if validator.alpha and not self._enable_alpha_validators:
                continue
            if self._can_run_validator(validator.code, validator.issue_type):
                issues.extend(validator.validate())

        return issues

    def _gather_validation_resources(self, request_schema: RequestSchema) -> ValidationResources:
        """Create validation resources from the request schema."""
        copy = request_schema.model_copy(deep=True)
        local = SchemaSnapshot(
            data_model={request_schema.data_model.as_reference(): copy.data_model},
            views={view.as_reference(): view for view in copy.views},
            containers={container.as_reference(): container for container in copy.containers},
            spaces={space.as_reference(): space for space in copy.spaces},
            node_types={node_type: node_type for node_type in copy.node_types},
            timestamp=datetime.now(timezone.utc),
        )

        return ValidationResources(
            cdf=self._cdf_snapshot,
            local=local,
            limits=self._limits,
            modus_operandi=self._modus_operandi,
        )

    def _deduplicate_actions(self, actions: list[FixAction]) -> list[FixAction]:
        """Remove duplicate fix actions based on code, resource_id, and field paths."""
        seen: dict[tuple, FixAction] = {}
        for action in actions:
            key = (action.code, action.resource_id, tuple(sorted(c.field_path for c in action.changes)))
            if key not in seen:
                seen[key] = action
        return list(seen.values())
