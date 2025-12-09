from collections.abc import Callable

from cognite.neat._client import NeatClient
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._data_model.validation.dms._connections import (
    ConnectionValueTypeUndefined,
    ConnectionValueTypeUnexisting,
    ReverseConnectionContainerMissing,
    ReverseConnectionContainerPropertyMissing,
    ReverseConnectionContainerPropertyWrongType,
    ReverseConnectionPointsToAncestor,
    ReverseConnectionSourcePropertyMissing,
    ReverseConnectionSourcePropertyWrongType,
    ReverseConnectionSourceViewMissing,
    ReverseConnectionTargetMismatch,
    ReverseConnectionTargetMissing,
)
from cognite.neat._data_model.validation.dms._limits import (
    ContainerPropertyCountIsOutOfLimits,
    ContainerPropertyListSizeIsOutOfLimits,
    DataModelViewCountIsOutOfLimits,
    ViewContainerCountIsOutOfLimits,
    ViewImplementsCountIsOutOfLimits,
    ViewPropertyCountIsOutOfLimits,
)
from cognite.neat._utils.useful_types import ModusOperandi

from ._ai_readiness import (
    DataModelMissingDescription,
    DataModelMissingName,
    EnumerationMissingDescription,
    EnumerationMissingName,
    ViewMissingDescription,
    ViewMissingName,
    ViewPropertyMissingDescription,
    ViewPropertyMissingName,
)
from ._base import DataModelValidator, CDFSnapshot, LocalSnapshot, ValidationResources
from ._consistency import ViewSpaceVersionInconsistentWithDataModel
from ._containers import (
    ExternalContainerDoesNotExist,
    ExternalContainerPropertyDoesNotExist,
    RequiredContainerDoesNotExist,
)
from ._views import ImplementedViewNotExisting, ViewToContainerMappingNotPossible


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
            # Limits
            DataModelViewCountIsOutOfLimits(validation_resources),
            ViewPropertyCountIsOutOfLimits(validation_resources),
            ViewImplementsCountIsOutOfLimits(validation_resources),
            ViewContainerCountIsOutOfLimits(validation_resources),
            ContainerPropertyCountIsOutOfLimits(validation_resources),
            ContainerPropertyListSizeIsOutOfLimits(validation_resources),
            # Views
            ViewToContainerMappingNotPossible(validation_resources),
            ImplementedViewNotExisting(validation_resources),
            # Containers
            ExternalContainerDoesNotExist(validation_resources),
            ExternalContainerPropertyDoesNotExist(validation_resources),
            RequiredContainerDoesNotExist(validation_resources),
            # Consistency
            ViewSpaceVersionInconsistentWithDataModel(validation_resources),
            # Connections
            ConnectionValueTypeUnexisting(validation_resources),
            ConnectionValueTypeUndefined(validation_resources),
            ReverseConnectionContainerMissing(validation_resources),
            ReverseConnectionContainerPropertyMissing(validation_resources),
            ReverseConnectionContainerPropertyWrongType(validation_resources),
            ReverseConnectionSourceViewMissing(validation_resources),
            ReverseConnectionSourcePropertyMissing(validation_resources),
            ReverseConnectionSourcePropertyWrongType(validation_resources),
            ReverseConnectionPointsToAncestor(validation_resources),
            ReverseConnectionTargetMismatch(validation_resources),
            ReverseConnectionTargetMissing(validation_resources),
            # AI Readiness
            DataModelMissingName(validation_resources),
            DataModelMissingDescription(validation_resources),
            ViewMissingName(validation_resources),
            ViewMissingDescription(validation_resources),
            ViewPropertyMissingName(validation_resources),
            ViewPropertyMissingDescription(validation_resources),
            EnumerationMissingName(validation_resources),
            EnumerationMissingDescription(validation_resources),
        ]

        # Run validators
        for validator in validators:
            if self._can_run_validator(validator.code, validator.issue_type):
                self._issues.extend(validator.run())

        self._has_run = True

    def _gather_validation_resources(self, request_schema: RequestSchema) -> ValidationResources:
        return ValidationResources(
            cdf=self._cdf_snapshot,
            local=LocalSnapshot.from_request_schema(request_schema),
            limits=self._limits,
            modus_operandi=self._modus_operandi,
        )