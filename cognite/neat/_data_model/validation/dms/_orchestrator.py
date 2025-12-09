from collections.abc import Callable

from cognite.neat._client import NeatClient
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._data_model.validation.dms._limits import (
    ContainerPropertyCountIsOutOfLimits,
    ContainerPropertyListSizeIsOutOfLimits,
    DataModelViewCountIsOutOfLimits,
    ViewContainerCountIsOutOfLimits,
    ViewImplementsCountIsOutOfLimits,
    ViewPropertyCountIsOutOfLimits,
)
from cognite.neat._utils.useful_types import ModusOperandi

from ._base import CDFResources, DataModelValidator, LocalResources, ValidationResources

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

# from ._connections import (
#     ConnectionValueTypeUndefined,
#     ConnectionValueTypeUnexisting,
#     ReverseConnectionContainerMissing,
#     ReverseConnectionContainerPropertyMissing,
#     ReverseConnectionContainerPropertyWrongType,
#     ReverseConnectionPointsToAncestor,
#     ReverseConnectionSourcePropertyMissing,
#     ReverseConnectionSourcePropertyWrongType,
#     ReverseConnectionSourceViewMissing,
#     ReverseConnectionTargetMismatch,
#     ReverseConnectionTargetMissing,
# )
# from ._consistency import ViewSpaceVersionInconsistentWithDataModel
# from ._containers import (
#     ExternalContainerDoesNotExist,
#     ExternalContainerPropertyDoesNotExist,
#     RequiredContainerDoesNotExist,
# )
# from ._views import ImplementedViewNotExisting, ViewToContainerMappingNotPossible


class DmsDataModelValidation(OnSuccessIssuesChecker):
    """Placeholder for DMS Quality Assessment functionality."""

    def __init__(
        self,
        client: NeatClient,
        modus_operandi: ModusOperandi = "additive",
        can_run_validator: Callable[[str, type], bool] | None = None,
    ) -> None:
        super().__init__()
        self._client = client
        self._can_run_validator = can_run_validator or (lambda code, issue_type: True)  # type: ignore
        self._modus_operandi = modus_operandi
        self._has_run = False

    def _gather_validation_resources(
        self, data_model: RequestSchema
    ) -> tuple[LocalResources, CDFResources, SchemaLimits]:
        """Gather local and CDF resources needed for validation."""

        local = LocalResources(
            data_model=data_model.data_model,
            views={view.as_reference(): view for view in data_model.views},
            containers={container.as_reference(): container for container in data_model.containers},
        )

        print("Fetching CDF resources for validation...")

        cdf = CDFResources(
            data_models={
                response.as_reference(): response.as_request()
                for response in self._client.data_models.retrieve([data_model.data_model.as_reference()])
            },
            views={
                response.as_reference(): response.as_request()
                for response in self._client.views.list(
                    all_versions=True, include_global=True, include_inherited_properties=False, limit=None
                )
            },
            containers={
                response.as_reference(): response.as_request()
                for response in self._client.containers.list(include_global=True, limit=None)
            },
            spaces={
                response.as_reference(): response.as_request()
                for response in self._client.spaces.list(include_global=True, limit=999)
            },
        )

        print("Fetching completed...")

        return ValidationResources(
            modus_operandi=self._modus_operandi,
            local=local,
            cdf=cdf,
            limits=SchemaLimits.from_api_response(self._client.statistics.project()),
        )

    def run(self, data_model: RequestSchema) -> None:
        """Run quality assessment on the DMS data model."""

        # Helper wrangled data model components
        validation_resources = self._gather_validation_resources(data_model)

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
            # ViewToContainerMappingNotPossible(validation_resources),
            # ImplementedViewNotExisting(local_resources, cdf_resources, self._modus_operandi),

            # # Containers
            # ExternalContainerDoesNotExist(local_resources, cdf_resources, self._modus_operandi),
            # ExternalContainerPropertyDoesNotExist(local_resources, cdf_resources, self._modus_operandi),
            # RequiredContainerDoesNotExist(local_resources, cdf_resources, self._modus_operandi),

            # # Consistency
            # ViewSpaceVersionInconsistentWithDataModel(local_resources, cdf_resources, self._modus_operandi),

            # # Connections
            # ConnectionValueTypeUnexisting(local_resources, cdf_resources, self._modus_operandi),
            # ConnectionValueTypeUndefined(local_resources, cdf_resources, self._modus_operandi),
            # ReverseConnectionContainerMissing(local_resources, cdf_resources, self._modus_operandi),
            # ReverseConnectionContainerPropertyMissing(local_resources, cdf_resources, self._modus_operandi),
            # ReverseConnectionContainerPropertyWrongType(local_resources, cdf_resources, self._modus_operandi),
            # ReverseConnectionSourceViewMissing(local_resources, cdf_resources, self._modus_operandi),
            # ReverseConnectionSourcePropertyMissing(local_resources, cdf_resources, self._modus_operandi),
            # ReverseConnectionSourcePropertyWrongType(local_resources, cdf_resources, self._modus_operandi),
            # ReverseConnectionPointsToAncestor(local_resources, cdf_resources, self._modus_operandi),
            # ReverseConnectionTargetMismatch(local_resources, cdf_resources, self._modus_operandi),
            # ReverseConnectionTargetMissing(local_resources, cdf_resources, self._modus_operandi),

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
