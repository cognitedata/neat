from pyparsing import cast

from cognite.neat._data_model._constants import DMSDefaultLimits
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._data_types import EnumProperty
from cognite.neat._data_model.models.dms._indexes import BtreeIndex, IndexDefinition, InvertedIndex
from cognite.neat._data_model.models.dms._references import ContainerReference, ViewReference
from cognite.neat._data_model.models.dms._view_property import (
    ViewCorePropertyRequest,
)
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._issues import ConsistencyError


class DataModelLimitValidator(DataModelValidator):
    """Validates that a DMS data model adheres to all CDF resource limits.

    This validator performs comprehensive limit checking across three levels:
    - Data Model Level
    - View Level
    - Container Level

    The validator supports two deployment modes:
    - **"replace" mode**: Validates only local data model resources
    - **"additive" mode**: Merges local + CDF resources for accurate limit checking

    All violations produce ConsistencyError issues that prevent deployment.
    """

    code = "NEAT-DMS-006"

    def run(self) -> list[ConsistencyError]:
        """Execute all limit validations on the data model.

        Performs three levels of validation:
        1. Data model limits (view count)
        2. View limits (properties, containers, implements)
        3. Container limits (properties, list sizes)

        Returns:
            List of ConsistencyError issues for any limit violations found.
            Empty list if all limits are satisfied.
        """
        errors: list[ConsistencyError] = []

        errors.extend(self._data_model_limit_check())
        errors.extend(self._views_limit_check())
        errors.extend(self._containers_limit_check())

        return errors

    def _data_model_limit_check(self) -> list[ConsistencyError]:
        """Validate that the data model does not exceed the maximum number of views.

        Checks that total view count (local + CDF in additive mode) does not exceed the limit.

        Returns:
            List with single ConsistencyError if limit exceeded, empty list otherwise.
        """

        if len(self.views_references) > DMSDefaultLimits.data_model.views_per_data_model:
            return [
                ConsistencyError(
                    message=(
                        f"The data model references {len(self.views_references)} views, which exceeds the limit of "
                        f"{DMSDefaultLimits.data_model.views_per_data_model} views per data model."
                    ),
                    code=self.code,
                )
            ]
        return []

    def _views_limit_check(self) -> list[ConsistencyError]:
        """Validate that no view exceeds properties, containers, or implements limits.

        For each view in the data model, checks:
        - Properties count
        - Unique container references
        - Implemented views count

        In additive mode, counts include properties and implements from both local
        and CDF versions of the view.

        Returns:
            List of ConsistencyError issues, one per limit violation found.
            Empty list if all views are within limits.
        """

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
        """Validate that no container exceeds properties or list size limits.

        For each container in the data model, checks:
        - Total properties count ≤ 100
        - List size (max_list_size) ≤ appropriate limit based on:
          * Data type (Int32, Int64, DirectRelation, etc.)
          * Presence of btree index
          * Default vs maximum limits

        Enum properties are skipped (have separate 32-value limit).

        In additive mode, counts include properties from both local and CDF
        versions of the container.

        Returns:
            List of ConsistencyError issues, one per limit violation found.
            Empty list if all containers are within limits.
        """

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
                        has_btree_index = (
                            property_id in properties_by_index_type[BtreeIndex.model_fields["index_type"].default]
                        )
                        max_allowed_limit = DMSDefaultLimits.container.get_limit_for_data_type(type_, has_btree_index)
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
        """Get all view references to validate based on deployment mode.

        In "replace" mode, returns only local view references.
        In "additive" mode, returns union of local and CDF view references.

        Returns:
            Set of ViewReference objects representing all views to validate.
        """

        return (
            set(self.local_resources.views_by_reference.keys()).union(set(self.cdf_resources.views_by_reference.keys()))
            if self.modus_operandi == "additive"
            else set(self.local_resources.views_by_reference.keys())
        )

    @property
    def container_references(self) -> set[ContainerReference]:
        """Get all container references to validate based on deployment mode.

        In "replace" mode, returns only local container references.
        In "additive" mode, returns union of local and CDF container references.

        Returns:
            Set of ContainerReference objects representing all containers to validate.
        """

        return (
            set(self.local_resources.containers_by_reference.keys()).union(
                set(self.cdf_resources.containers_by_reference.keys())
            )
            if self.modus_operandi == "additive"
            else set(self.local_resources.containers_by_reference.keys())
        )

    @property
    def merged_views(self) -> dict[ViewReference, ViewRequest]:
        """Get views with merged properties and implements for accurate limit checking.

        In "replace" mode, returns only local views.
        In "additive" mode, merges local and CDF views by:
        - Combining properties from both versions (local overrides CDF)
        - Combining implements lists (union, no duplicates)
        - Using CDF view as base if it exists, otherwise local view

        This ensures limit validation accounts for the actual deployed state
        in additive deployments.

        Returns:
            Dictionary mapping ViewReference to merged ViewRequest objects.

        Raises:
            RuntimeError: If a referenced view is not found in either local or CDF resources.
        """

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
                    for impl in local_view.implements:
                        if impl not in cast(list[ViewReference], merged_views[view_ref].implements):
                            cast(list[ViewReference], merged_views[view_ref].implements).append(impl)

        return merged_views

    @property
    def merged_containers(self) -> dict[ContainerReference, ContainerRequest]:
        """Get containers with merged properties for accurate limit checking.

        In "replace" mode, returns only local containers.
        In "additive" mode, merges local and CDF containers by:
        - Combining properties from both versions (local overrides CDF)
        - Using CDF container as base if it exists, otherwise local container

        This ensures limit validation accounts for the actual deployed state
        in additive deployments.

        Returns:
            Dictionary mapping ContainerReference to merged ContainerRequest objects.

        Raises:
            RuntimeError: If a referenced container is not found in either local or CDF resources.
        """

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
        """Map container properties to their index types for limit validation.

        Categorizes container properties by their index configuration:
        - "btree": Properties with btree indexes (have stricter list size limits)
        - "inverted": Properties with inverted indexes

        This mapping is used to determine the appropriate list size limit for
        each property based on whether it has a btree index.

        Args:
            container: The container to analyze.

        Returns:
            Dictionary with index type strings as keys and lists of property identifiers
            as values. Returns empty lists for both index types if container has no indexes.
        """

        container_property_by_index_type: dict[str, list] = {
            BtreeIndex.model_fields["index_type"].default: [],
            InvertedIndex.model_fields["index_type"].default: [],
        }
        if not container.indexes:
            return container_property_by_index_type

        for index in container.indexes.values():
            if isinstance(index, BtreeIndex):
                container_property_by_index_type[BtreeIndex.model_fields["index_type"].default].extend(index.properties)
            elif isinstance(index, IndexDefinition):
                container_property_by_index_type[IndexDefinition.model_fields["index_type"].default].extend(
                    index.properties
                )

        return container_property_by_index_type
