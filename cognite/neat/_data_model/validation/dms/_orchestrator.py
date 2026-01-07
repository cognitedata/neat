from collections.abc import Callable
from datetime import datetime, timezone

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.useful_types import ModusOperandi

from ._base import DataModelValidator


class DmsDataModelValidation(OnSuccessIssuesChecker):
    """Placeholder for DMS Quality Assessment functionality."""

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
        validators: list[DataModelValidator] = [
            validator(validation_resources) for validator in get_concrete_subclasses(DataModelValidator)
        ]

        # Run validators
        for validator in validators:
            if validator.alpha and not self._enable_alpha_validators:
                continue
            if self._can_run_validator(validator.code, validator.issue_type):
                self._issues.extend(validator.run())

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
