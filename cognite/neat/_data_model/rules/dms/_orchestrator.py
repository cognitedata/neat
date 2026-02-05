from collections.abc import Callable

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._fix_actions import FixAction
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._data_model.rules.dms._base import DataModelRule
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

    def run(self, request_schema: RequestSchema) -> None:
        """Run quality assessment on the DMS data model."""
        if self._apply_fixes:
            validation_resources = self._gather_validation_resources(request_schema)
            fix_actions = self._collect_fix_actions(validation_resources)

            # Create thin snapshot for O(1) lookup - mutations flow through to request_schema
            fix_snapshot = SchemaSnapshot.from_request_schema(request_schema, deep_copy=False)
            for action in fix_actions:
                action(fix_snapshot)
                self._applied_fixes.append(action)

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
        # Deep copy for validation - we don't want to modify the original during merge/analysis
        local = SchemaSnapshot.from_request_schema(request_schema, deep_copy=True)

        return ValidationResources(
            cdf=self._cdf_snapshot,
            local=local,
            limits=self._limits,
            modus_operandi=self._modus_operandi,
        )

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
