from pyparsing import cast

from cognite.neat._data_model._constants import DMSDefaultLimits
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._data_types import EnumProperty
from cognite.neat._data_model.models.dms._indexes import BtreeIndex, IndexDefinition
from cognite.neat._data_model.models.dms._references import ContainerReference, ViewReference
from cognite.neat._data_model.models.dms._view_property import (
    ViewCorePropertyRequest,
)
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError


class DataModelLimitValidator(DataModelValidator):
    """This data model validator checks that the data model adheres to DMS limits."""

    code = "NEAT-DMS-006"

    def run(self) -> list[ConsistencyError]:
        errors: list[ConsistencyError] = []

        errors.extend(self._data_model_limit_check())
        errors.extend(self._views_limit_check())
        errors.extend(self._containers_limit_check())

        return errors

    def _data_model_limit_check(self) -> list[ConsistencyError]:
        """Get the data model view limits."""

        if len(self.container_references) > DMSDefaultLimits.data_model.views_per_data_model:
            return [
                ConsistencyError(
                    message=(
                        f"The data model references {len(self.container_references)} views, which exceeds the limit of "
                        f"{DMSDefaultLimits.data_model.views_per_data_model} views per data model."
                    ),
                    code=self.code,
                )
            ]
        return []

    def _views_limit_check(self) -> list[ConsistencyError]:
        """Check that no view exceeds the properties limit."""

        errors: list[ConsistencyError] = []

        merged_views = self.merged_views

        for view_ref in self.local_resources.views_by_reference.keys():
            view = merged_views.get(view_ref)
            if not view:
                raise RuntimeError(f"View {view_ref!s} not found in merged views. This is a bug!")

            if view.properties:
                if len(view.properties) > DMSDefaultLimits.view.properties_per_view:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"View {view_ref!s} has {len(view.properties)} properties, which exceeds the limit of "
                                f"{DMSDefaultLimits.view.properties_per_view} properties per view."
                            ),
                            code=self.code,
                        )
                    )

                if (
                    count := len(
                        {
                            prop.container
                            for prop in view.properties.values()
                            if (isinstance(prop, ViewCorePropertyRequest) and prop.container)
                        }
                    )
                ) and count > DMSDefaultLimits.view.containers_per_view:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"View {view_ref!s} references "
                                f"{count} containers, which exceeds the limit of "
                                f"{DMSDefaultLimits.view.containers_per_view} containers per view."
                            ),
                            code=self.code,
                        )
                    )

            if view.implements:
                if len(view.implements) > DMSDefaultLimits.view.implements_per_view:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"View {view_ref!s} implements {len(view.implements)} views, which exceeds the limit of"
                                f" {DMSDefaultLimits.view.implements_per_view} implemented views per view."
                            ),
                            code=self.code,
                        )
                    )

        return errors

    def _containers_limit_check(self) -> list[ConsistencyError]:
        """Check that no container exceeds the properties limit."""

        errors: list[ConsistencyError] = []

        merged_containers = self.merged_containers

        for container_ref in self.local_resources.containers_by_reference.keys():
            container = merged_containers.get(container_ref)
            if not container:
                raise RuntimeError(f"Container {container_ref!s} not found in merged containers. This is a bug!")

            if container.properties:
                properties_by_index_type = self.container_property_by_index_type(container)

                if len(container.properties) > DMSDefaultLimits.container.properties_per_container:
                    errors.append(
                        ConsistencyError(
                            message=(
                                f"Container {container_ref!s} has {len(container.properties)} properties, "
                                "which exceeds the limit of "
                                f"{DMSDefaultLimits.container.properties_per_container} properties per container."
                            ),
                            code=self.code,
                        )
                    )

                for property_id, property_ in container.properties.items():
                    type_ = property_.type

                    if isinstance(type_, EnumProperty):
                        continue

                    if type_.list and hasattr(type_, "max_list_size") and type_.max_list_size:
                        has_btree_index = property_id in properties_by_index_type[BtreeIndex.index_type]
                        max_allowed_limit = DMSDefaultLimits.container.listable_property.get_limit_for_data_type(
                            type_, has_btree_index
                        )
                        if type_.max_list_size > max_allowed_limit:
                            errors.append(
                                ConsistencyError(
                                    message=(
                                        f"Container {container_ref!s} has property {property_id} with list size "
                                        f"{type_.max_list_size}, which exceeds the limit of {max_allowed_limit} "
                                        f"for data type {type_.__class__.__name__}."
                                    ),
                                    code=self.code,
                                )
                            )

        return errors

    @property
    def views_references(self) -> set[ViewReference]:
        """Get all view references based on the modus operandi."""

        return (
            set(self.local_resources.views_by_reference.keys()).union(set(self.cdf_resources.views_by_reference.keys()))
            if self.modus_operandi == "additive"
            else set(self.local_resources.views_by_reference.keys())
        )

    @property
    def container_references(self) -> set[ContainerReference]:
        """Get all container references based on the modus operandi."""

        return (
            set(self.local_resources.containers_by_reference.keys()).union(
                set(self.cdf_resources.containers_by_reference.keys())
            )
            if self.modus_operandi == "additive"
            else set(self.local_resources.containers_by_reference.keys())
        )

    @property
    def merged_views(self) -> dict[ViewReference, ViewRequest]:
        """Get the number of properties for each view based on the modus operandi."""

        if self.modus_operandi != "additive":
            return self.local_resources.views_by_reference

        merged_views: dict[ViewReference, ViewRequest] = {}
        # Merge local views, combining properties if view exists in both
        for view_ref in self.views_references:
            cdf_view = self.cdf_resources.views_by_reference.get(view_ref)
            local_view = self.local_resources.views_by_reference.get(view_ref)

            if not cdf_view and not local_view:
                raise RuntimeError(f"View {view_ref!s} not found in either local or CDF resources. This is a bug!")

            # this will later update of local properties and implements
            merged_views[view_ref] = cast(ViewRequest, cdf_view or local_view)

            if local_view and local_view.properties:
                if not merged_views[view_ref].properties:
                    merged_views[view_ref].properties = local_view.properties
                else:
                    merged_views[view_ref].properties.update(local_view.properties)

            if local_view and local_view.implements:
                if not merged_views[view_ref].implements:
                    merged_views[view_ref].implements = local_view.implements
                else:  # mypy is complaining here about possible None which is not possible due to the check above
                    cast(list[ViewReference], merged_views[view_ref].implements).extend(local_view.implements)

        return merged_views

    @property
    def merged_containers(self) -> dict[ContainerReference, ContainerRequest]:
        """Get the number of properties for each container based on the modus operandi."""

        if self.modus_operandi != "additive":
            return self.local_resources.containers_by_reference

        merged_containers: dict[ContainerReference, ContainerRequest] = {}
        # Merge local views, combining properties if view exists in both
        for view_ref in self.container_references:
            cdf_container = self.cdf_resources.containers_by_reference.get(view_ref)
            local_container = self.local_resources.containers_by_reference.get(view_ref)

            if not cdf_container and not local_container:
                raise RuntimeError(f"Container {view_ref!s} not found in either local or CDF resources. This is a bug!")

            merged_containers[view_ref] = cast(ContainerRequest, cdf_container or local_container)

            if local_container and local_container.properties:
                if not merged_containers[view_ref].properties:
                    merged_containers[view_ref].properties = local_container.properties
                else:
                    merged_containers[view_ref].properties.update(local_container.properties)

        return merged_containers

    def container_property_by_index_type(self, container: ContainerRequest) -> dict[str, list]:
        """Get the container properties by index type."""

        container_property_by_index_type: dict[str, list] = {BtreeIndex.index_type: [], IndexDefinition.index_type: []}

        if not container.indexes:
            return container_property_by_index_type

        for index in container.indexes.values():
            if isinstance(index, BtreeIndex):
                container_property_by_index_type[BtreeIndex.index_type].append(index.properties)
            elif isinstance(index, IndexDefinition):
                container_property_by_index_type[IndexDefinition.index_type].append(index.properties)

        return container_property_by_index_type
