from itertools import chain

from cognite.neat._client import NeatClient
from cognite.neat._data_model._analysis import DataModelAnalysis
from cognite.neat._data_model._shared import OnSuccessIssuesChecker
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._references import ContainerReference, ViewReference
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._data_model.validation._base import DataModelValidator

from ._validators import (
    BidirectionalConnectionMisconfigured,
    UndefinedConnectionEndNodeTypes,
    VersionSpaceInconsistency,
    ViewsWithoutProperties,
)


class DmsDataModelValidation(OnSuccessIssuesChecker):
    """Placeholder for DMS Quality Assessment functionality."""

    def __init__(
        self, client: NeatClient | None = None, codes: list[str] | None = None, modus_operandi: str | None = None
    ) -> None:
        super().__init__(client)
        self._codes = codes or ["all"]
        self._modus_operandi = modus_operandi  # will be used later to trigger how validators will behave

    def run(self, data_model: RequestSchema) -> None:
        """Run quality assessment on the DMS data model."""

        # Helper wrangled data model components
        analysis = DataModelAnalysis(data_model)
        local_views_by_reference = analysis.view_by_reference(include_inherited_properties=True)
        local_connection_end_node_types = analysis.connection_end_node_types
        local_ancestors_by_view_reference = analysis.ancestors_by_view(list(local_views_by_reference.values()))
        cdf_views_by_reference = self._cdf_view_by_reference(
            list(analysis.referenced_views(include_connection_end_node_types=True)),
            include_inherited_properties=True,
        )
        cdf_ancestors_by_view_reference = analysis.ancestors_by_view(list(cdf_views_by_reference.values()))

        reverse_to_direct_mapping = analysis.reverse_to_direct_mapping
        local_containers_by_reference = analysis.container_by_reference
        cdf_containers_by_reference = self._cdf_container_by_reference(
            list(self._referenced_containers(local_views_by_reference, cdf_views_by_reference))
        )

        validators: list[DataModelValidator] = [
            ViewsWithoutProperties(
                local_views_by_reference=local_views_by_reference,
                cdf_views_by_reference=cdf_views_by_reference,
            ),
            UndefinedConnectionEndNodeTypes(
                local_connection_end_node_types=local_connection_end_node_types,
                local_views_by_reference=local_views_by_reference,
                cdf_views_by_reference=cdf_views_by_reference,
            ),
            VersionSpaceInconsistency(
                data_model_reference=data_model.data_model.as_reference(),
                view_references=list(local_views_by_reference.keys()),
            ),
            BidirectionalConnectionMisconfigured(
                local_views_by_reference=local_views_by_reference,
                cdf_views_by_reference=cdf_views_by_reference,
                local_ancestors_by_view_reference=local_ancestors_by_view_reference,
                cdf_ancestors_by_view_reference=cdf_ancestors_by_view_reference,
                reverse_to_direct_mapping=reverse_to_direct_mapping,
                local_containers_by_reference=local_containers_by_reference,
                cdf_containers_by_reference=cdf_containers_by_reference,
            ),
        ]

        for validator in validators:
            if "all" in self._codes or validator.code in self._codes:
                self._issues.extend(validator.run())

        self._has_run = True

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
