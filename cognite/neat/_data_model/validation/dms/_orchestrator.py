from collections.abc import Callable
from itertools import chain

from cognite.neat._client import NeatClient
from cognite.neat._data_model._analysis import DataModelAnalysis
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._references import ContainerReference, DataModelReference, ViewReference
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.models.dms._views import ViewRequest
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
from ._base import CDFResources, DataModelValidator, LocalResources, ValidationResources
from ._connections import (
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
        cdf_resources: CDFResources,
        limits: SchemaLimits | None = None,
        modus_operandi: ModusOperandi = "additive",
        can_run_validator: Callable[[str, type], bool] | None = None,
    ) -> None:
        super().__init__()
        self._cdf_resources = cdf_resources
        self._limits = limits or SchemaLimits()
        self._can_run_validator = can_run_validator or (lambda code, issue_type: True)  # type: ignore
        self._modus_operandi = modus_operandi
        self._has_run = False

    def _gather_validation_resources(self, data_model: RequestSchema) -> tuple[LocalResources, CDFResources, SchemaLimits]:
        """Gather local and CDF resources needed for validation."""


        local = LocalResources(data_model=data_model.data_model,
                               views = {view.as_reference(): view for view in data_model.data_model.views},
                               containers = {container.as_reference(): container for container in data_model.data_model.containers})

        return ValidationResources(modus_operandi=self._modus_operandi, local=local, cdf=self._cdf_resources, limits=self._limits)

    def run(self, data_model: RequestSchema) -> None:
        """Run quality assessment on the DMS data model."""

        # Helper wrangled data model components
        local_resources, cdf_resources, cdf_limits = self._gather_resources(data_model)

        # Initialize all validators
        validators: list[DataModelValidator] = [
            # Limits
            DataModelViewCountIsOutOfLimits(local_resources, cdf_resources, cdf_limits, self._modus_operandi),
            ViewPropertyCountIsOutOfLimits(local_resources, cdf_resources, cdf_limits, self._modus_operandi),
            ViewImplementsCountIsOutOfLimits(local_resources, cdf_resources, cdf_limits, self._modus_operandi),
            ViewContainerCountIsOutOfLimits(local_resources, cdf_resources, cdf_limits, self._modus_operandi),
            ContainerPropertyCountIsOutOfLimits(local_resources, cdf_resources, cdf_limits, self._modus_operandi),
            ContainerPropertyListSizeIsOutOfLimits(local_resources, cdf_resources, cdf_limits, self._modus_operandi),
            # Views
            ViewToContainerMappingNotPossible(local_resources, cdf_resources, self._modus_operandi),
            ImplementedViewNotExisting(local_resources, cdf_resources, self._modus_operandi),
            # Containers
            ExternalContainerDoesNotExist(local_resources, cdf_resources, self._modus_operandi),
            ExternalContainerPropertyDoesNotExist(local_resources, cdf_resources, self._modus_operandi),
            RequiredContainerDoesNotExist(local_resources, cdf_resources, self._modus_operandi),
            # Consistency
            ViewSpaceVersionInconsistentWithDataModel(local_resources, cdf_resources, self._modus_operandi),
            # Connections
            ConnectionValueTypeUnexisting(local_resources, cdf_resources, self._modus_operandi),
            ConnectionValueTypeUndefined(local_resources, cdf_resources, self._modus_operandi),
            ReverseConnectionContainerMissing(local_resources, cdf_resources, self._modus_operandi),
            ReverseConnectionContainerPropertyMissing(local_resources, cdf_resources, self._modus_operandi),
            ReverseConnectionContainerPropertyWrongType(local_resources, cdf_resources, self._modus_operandi),
            ReverseConnectionSourceViewMissing(local_resources, cdf_resources, self._modus_operandi),
            ReverseConnectionSourcePropertyMissing(local_resources, cdf_resources, self._modus_operandi),
            ReverseConnectionSourcePropertyWrongType(local_resources, cdf_resources, self._modus_operandi),
            ReverseConnectionPointsToAncestor(local_resources, cdf_resources, self._modus_operandi),
            ReverseConnectionTargetMismatch(local_resources, cdf_resources, self._modus_operandi),
            ReverseConnectionTargetMissing(local_resources, cdf_resources, self._modus_operandi),
            # AI Readiness
            DataModelMissingName(local_resources, cdf_resources, self._modus_operandi),
            DataModelMissingDescription(local_resources, cdf_resources, self._modus_operandi),
            ViewMissingName(local_resources, cdf_resources, self._modus_operandi),
            ViewMissingDescription(local_resources, cdf_resources, self._modus_operandi),
            ViewPropertyMissingName(local_resources, cdf_resources, self._modus_operandi),
            ViewPropertyMissingDescription(local_resources, cdf_resources, self._modus_operandi),
            EnumerationMissingName(local_resources, cdf_resources, self._modus_operandi),
            EnumerationMissingDescription(local_resources, cdf_resources, self._modus_operandi),
        ]

        # Run validators
        for validator in validators:
            if self._can_run_validator(validator.code, validator.issue_type):
                self._issues.extend(validator.run())

        self._has_run = True

    def _cdf_data_model_views(self, data_model_ref: DataModelReference) -> set[ViewReference]:
        """Get all data model views in CDF."""

        if not self._client:
            return set()

        data_model = self._client.data_models.retrieve([data_model_ref])

        return set(data_model[0].views) if data_model and data_model[0].views else set()

    def _cdf_view_by_reference(
        self, views: list[ViewReference], include_inherited_properties: bool = True
    ) -> dict[ViewReference, ViewRequest]:
        """Fetch view definition from CDF."""

        if not self._client:
            return {}
        return {
            response.as_reference(): response.as_request()
            for response in self._client.views.retrieve(
                views, include_inherited_properties=include_inherited_properties
            )
        }

    def _cdf_container_by_reference(
        self, containers: list[ContainerReference]
    ) -> dict[ContainerReference, ContainerRequest]:
        """Fetch container definition from CDF."""

        if not self._client:
            return {}
        return {
            response.as_reference(): response.as_request() for response in self._client.containers.retrieve(containers)
        }

    def _cdf_limits(self) -> SchemaLimits:
        """Fetch DMS statistics from CDF."""

        if not self._client:
            return SchemaLimits()
        return SchemaLimits.from_api_response(self._client.statistics.project())

    def _referenced_containers(
        self,
        local_views_by_reference: dict[ViewReference, ViewRequest],
        cdf_views_by_reference: dict[ViewReference, ViewRequest],
    ) -> set[ContainerReference]:
        """Get all referenced containers in the physical data model both local and in CDF."""
        return {
            property_.container
            for view in chain(local_views_by_reference.values(), cdf_views_by_reference.values())
            if view.properties
            for property_ in view.properties.values()
            if isinstance(property_, ViewCorePropertyRequest)
        }
