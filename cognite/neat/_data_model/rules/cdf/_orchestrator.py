from collections.abc import Callable

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._utils.auxiliary import get_concrete_subclasses

from ._base import CDFRule


class CDFRulesOrchestrator(OnSuccessIssuesChecker):
    """Placeholder for DMS Quality Assessment functionality."""

    def __init__(
        self,
        limits: SchemaLimits,
        can_run_validator: Callable[[str, type], bool] | None = None,
        enable_alpha_validators: bool = False,
    ) -> None:
        super().__init__()
        self._limits = limits
        self._can_run_validator = can_run_validator or (lambda code, issue_type: True)  # type: ignore
        self._has_run = False
        self._enable_alpha_validators = enable_alpha_validators

    def run(self, cdf_snapshot: SchemaSnapshot) -> None:
        """Run quality assessment on the DMS data model."""

        validation_resources = self._gather_validation_resources(cdf_snapshot)

        # Initialize all validators
        validators: list[CDFRule] = [validator(validation_resources) for validator in get_concrete_subclasses(CDFRule)]

        # Run validators
        for validator in validators:
            if validator.alpha and not self._enable_alpha_validators:
                continue
            if self._can_run_validator(validator.code, validator.issue_type):
                self._issues.extend(validator.validate())

        self._has_run = True

    def _gather_validation_resources(self, cdf_snapshot: SchemaSnapshot) -> ValidationResources:
        # we do not want to modify the original request schema during validation

        return ValidationResources(
            cdf=cdf_snapshot,
            local=cdf_snapshot,
            limits=self._limits,
            modus_operandi="rebuild",
        )
