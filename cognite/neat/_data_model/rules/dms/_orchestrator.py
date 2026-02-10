from collections import defaultdict
from collections.abc import Callable

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._fix import FixAction
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms import SchemaResourceId
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
    ) -> None:
        super().__init__()
        self._cdf_snapshot = cdf_snapshot
        self._limits = limits
        self._modus_operandi = modus_operandi
        self._can_run_validator = can_run_validator or (lambda code, issue_type: True)  # type: ignore
        self._has_run = False
        self._enable_alpha_validators = enable_alpha_validators
        self._fixes_by_resource_id: dict[SchemaResourceId, list[FixAction]] = defaultdict(list)

    def run(self, request_schema: RequestSchema) -> None:
        """Validate the schema: run all validators and collect fix actions from fixable ones.

        After calling this, self.issues contains the validation issues and
        self.pending_fixes contains any available fix actions.
        """
        validation_resources = self._gather_validation_resources(request_schema)
        validators: list[DataModelRule] = [
            validator(validation_resources) for validator in get_concrete_subclasses(DataModelRule)
        ]

        for validator in validators:
            if validator.alpha and not self._enable_alpha_validators:
                continue
            if self._can_run_validator(validator.code, validator.issue_type):
                self._issues.extend(validator.validate())
                if validator.fixable:
                    for action in validator.fix():
                        self._fixes_by_resource_id[action.resource_id].append(action)

        self._has_run = True

    @property
    def pending_fixes(self) -> list[FixAction]:
        """Return the collected fix actions (not yet applied)."""
        return [action for actions in self._fixes_by_resource_id.values() for action in actions]

    def _gather_validation_resources(self, request_schema: RequestSchema) -> ValidationResources:
        # Deep copy for validation - we don't want to modify the original during merge/analysis
        local = SchemaSnapshot.from_request_schema(request_schema, deep_copy=True)

        return ValidationResources(
            cdf=self._cdf_snapshot,
            local=local,
            limits=self._limits,
            modus_operandi=self._modus_operandi,
        )
