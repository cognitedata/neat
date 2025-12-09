from collections.abc import Callable

from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.useful_types import ModusOperandi

from ._base import CDFSnapshot, DataModelValidator, LocalSnapshot, ValidationResources


class DmsDataModelValidation(OnSuccessIssuesChecker):
    """Placeholder for DMS Quality Assessment functionality."""

    def __init__(
        self,
        cdf_snapshot: CDFSnapshot,
        limits: SchemaLimits,
        modus_operandi: ModusOperandi = "additive",
        can_run_validator: Callable[[str, type], bool] | None = None,
    ) -> None:
        super().__init__()
        self._cdf_snapshot = cdf_snapshot
        self._limits = limits
        self._modus_operandi = modus_operandi
        self._can_run_validator = can_run_validator or (lambda code, issue_type: True)  # type: ignore
        self._has_run = False

    def run(self, request_schema: RequestSchema) -> None:
        """Run quality assessment on the DMS data model."""

        validation_resources = self._gather_validation_resources(request_schema)

        # Initialize all validators
        validators: list[DataModelValidator] = [
            cls(validation_resources) for cls in get_concrete_subclasses(DataModelValidator)
        ]

        # Run validators
        for validator in validators:
            if self._can_run_validator(validator.code, validator.issue_type):
                self._issues.extend(validator.run())

        self._has_run = True

    def _gather_validation_resources(self, request_schema: RequestSchema) -> ValidationResources:
        return ValidationResources(
            cdf=self._cdf_snapshot,
            local=LocalSnapshot.from_request_schema(request_schema.model_copy(deep=True)),
            limits=self._limits,
            modus_operandi=self._modus_operandi,
        )
