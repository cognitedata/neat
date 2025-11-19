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

from ._base import CDFResources, DataModelValidator, LocalResources
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
from ._views import ViewToContainerMappingNotPossible


class DmsDataModelValidation(OnSuccessIssuesChecker):
    """Placeholder for DMS Quality Assessment functionality."""

    def __init__(
        self,
        client: NeatClient | None = None,
        codes: list[str] | None = None,
        modus_operandi: ModusOperandi = "additive",
    ) -> None:
        super().__init__()
        self._client = client
        self._codes = codes or ["all"]
        self._modus_operandi = modus_operandi
        self._has_run = False

    def _gather_resources(self, data_model: RequestSchema) -> tuple[LocalResources, CDFResources, SchemaLimits]:
        """Gather local and CDF resources needed for validation."""

        analysis = DataModelAnalysis(data_model)

        local_views_by_reference = analysis.view_by_reference(include_inherited_properties=True)
        local_ancestors_by_view_reference = analysis.ancestors_by_view(list(local_views_by_reference.values()))
        local_reverse_to_direct_mapping = analysis.reverse_to_direct_mapping
        local_containers_by_reference = analysis.container_by_reference
        local_data_model_views = set(data_model.data_model.views) if data_model.data_model.views else set()

        local_resources = LocalResources(
            data_model_reference=data_model.data_model.as_reference(),
            views_by_reference=local_views_by_reference,
            ancestors_by_view_reference=local_ancestors_by_view_reference,
            reverse_to_direct_mapping=local_reverse_to_direct_mapping,
            containers_by_reference=local_containers_by_reference,
            connection_end_node_types=analysis.connection_end_node_types,
            data_model_views=local_data_model_views,
        )

        cdf_views_by_reference = self._cdf_view_by_reference(
            list(analysis.referenced_views(include_connection_end_node_types=True)),
            include_inherited_properties=True,
        )
        cdf_ancestors_by_view_reference = analysis.ancestors_by_view(list(cdf_views_by_reference.values()))
        cdf_containers_by_reference = self._cdf_container_by_reference(
            list(self._referenced_containers(local_views_by_reference, cdf_views_by_reference))
        )
        cdf_data_model_views = self._cdf_data_model_views(data_model.data_model.as_reference())

        cdf_resources = CDFResources(
            views_by_reference=cdf_views_by_reference,
            ancestors_by_view_reference=cdf_ancestors_by_view_reference,
            containers_by_reference=cdf_containers_by_reference,
            data_model_views=cdf_data_model_views,
        )

        return local_resources, cdf_resources, self._cdf_limits()

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
        ]

        # Run validators
        for validator in validators:
            if "all" in self._codes or validator.code in self._codes:
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
