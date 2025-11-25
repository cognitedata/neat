from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import chain
from typing import ClassVar, TypeAlias, cast

from pyparsing import cached_property

from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._references import (
    ContainerDirectReference,
    ContainerReference,
    DataModelReference,
    ViewDirectReference,
    ViewReference,
)
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._issues import ConsistencyError, Recommendation
from cognite.neat._utils.useful_types import ModusOperandi

# Type aliases for better readability
ViewsByReference: TypeAlias = dict[ViewReference, ViewRequest]
ContainersByReference: TypeAlias = dict[ContainerReference, ContainerRequest]
AncestorsByReference: TypeAlias = dict[ViewReference, set[ViewReference]]
ReverseToDirectMapping: TypeAlias = dict[
    tuple[ViewReference, str], tuple[ViewReference, ContainerDirectReference | ViewDirectReference]
]
ConnectionEndNodeTypes: TypeAlias = dict[tuple[ViewReference, str], ViewReference | None]


@dataclass
class LocalResources:
    """Local data model resources."""

    data_model_reference: DataModelReference
    views_by_reference: ViewsByReference
    ancestors_by_view_reference: AncestorsByReference
    reverse_to_direct_mapping: ReverseToDirectMapping
    containers_by_reference: ContainersByReference
    connection_end_node_types: ConnectionEndNodeTypes
    data_model_views: set[ViewReference]


@dataclass
class CDFResources:
    """CDF resources."""

    views_by_reference: ViewsByReference
    ancestors_by_view_reference: AncestorsByReference
    containers_by_reference: ContainersByReference
    data_model_views: set[ViewReference]


class DataModelValidator(ABC):
    """Assessors for fundamental data model principles."""

    code: ClassVar[str]

    def __init__(
        self,
        local_resources: LocalResources,
        cdf_resources: CDFResources,
        modus_operandi: ModusOperandi = "additive",
    ) -> None:
        self.local_resources = local_resources
        self.cdf_resources = cdf_resources
        self.modus_operandi = modus_operandi

    @abstractmethod
    def run(self) -> list[ConsistencyError] | list[Recommendation] | list[ConsistencyError | Recommendation]:
        """Execute the success handler on the data model."""
        # do something with data model
        ...

    def _select_view_with_property(self, view_ref: ViewReference, property_: str) -> ViewRequest | None:
        """Select the appropriate view (local or CDF) that contains desired property.

        Prioritizes views that contain the property  (first local than CDF),
        then falls back to any available view (even without the property).

        Args:
            view_ref: Reference to the view.
            property_: Property name to look for.

        Returns:
            The selected ViewRequest if found, else None.

        !! note "Behavior based on modus operandi"
            - In "additive" modus operandi, local and CDF view will be considered irrirespective of their space.
            - In "rebuild" modus operandi, local views will be considered irrispective of their space, while CDF views
              will only be considered if they belong to the different space than the local data model space
              (as they are considered external resources that is managed under other data model/schema space).

        """

        local_view = self.local_resources.views_by_reference.get(view_ref)
        cdf_view = (
            self.cdf_resources.views_by_reference.get(view_ref)
            if view_ref.space != self.local_resources.data_model_reference.space or self.modus_operandi == "additive"
            else None
        )

        # Try views with the property first, then any available view
        candidates = chain(
            (v for v in (local_view, cdf_view) if v and v.properties and property_ in v.properties),
            (v for v in (local_view, cdf_view) if v),
        )

        return next(candidates, None)

    def _select_container_with_property(
        self, container_ref: ContainerReference, property_: str
    ) -> ContainerRequest | None:
        """Select the appropriate container (local or CDF) that contains the desired property.

        Prioritizes containers that contain the property (first local than CDF),
        then falls back to any available container.

        Args:
            container_ref: Reference to the container.
            property_: Property name to look for.

        Returns:
            The selected ContainerRequest if found, else None.

        !! note "Behavior based on modus operandi"
            - In "additive" modus operandi, local and CDF containers will be considered irrirespective of their space.
            - In "rebuild" modus operandi, local containers will be considered irrispective of their space, while CDF
              containers will only be considered if they belong to the different space than the local data model space
              (as they are considered external resources that is managed under other data model/schema space).

        """
        local_container = self.local_resources.containers_by_reference.get(container_ref)
        cdf_container = self.cdf_resources.containers_by_reference.get(container_ref)

        cdf_container = (
            self.cdf_resources.containers_by_reference.get(container_ref)
            if container_ref.space != self.local_resources.data_model_reference.space
            or self.modus_operandi == "additive"
            else None
        )

        # Try containers with the property first, then any available container
        candidates = chain(
            (c for c in (local_container, cdf_container) if c and c.properties and property_ in c.properties),
            (c for c in (local_container, cdf_container) if c),
        )

        return next(candidates, None)

    @cached_property
    def data_model_view_references(self) -> set[ViewReference]:
        """Get all data model view references to validate based on deployment mode.

        In "rebuild" mode, returns only local data model view references.
        In "additive" mode, returns union of local and CDF data model view references.

        Returns:
            Set of ViewReference objects representing all data model views to validate.
        """
        return (
            self.local_resources.data_model_views.union(self.cdf_resources.data_model_views)
            if self.modus_operandi == "additive"
            else self.local_resources.data_model_views
        )

    @cached_property
    def views_references(self) -> set[ViewReference]:
        """Get all view references to validate based on deployment mode.

        In "rebuild" mode, returns only local view references.
        In "additive" mode, returns union of local and CDF view references.

        Returns:
            Set of ViewReference objects representing all views to validate.
        """

        return (
            set(self.local_resources.views_by_reference.keys()).union(set(self.cdf_resources.views_by_reference.keys()))
            if self.modus_operandi == "additive"
            else set(self.local_resources.views_by_reference.keys())
        )

    @cached_property
    def container_references(self) -> set[ContainerReference]:
        """Get all container references to validate based on deployment mode.

        In "rebuild" mode, returns only local container references.
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

    @cached_property
    def merged_views(self) -> dict[ViewReference, ViewRequest]:
        """Get views with merged properties and implements for accurate limit checking.

        In "rebuild" mode, returns only local views.
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
            merged_views[view_ref] = cast(ViewRequest, (cdf_view or local_view)).model_copy(deep=True)

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

    @cached_property
    def merged_containers(self) -> dict[ContainerReference, ContainerRequest]:
        """Get containers with merged properties for accurate limit checking.

        In "rebuild" mode, returns only local containers.
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

            merged_containers[view_ref] = cast(ContainerRequest, (cdf_container or local_container)).model_copy(
                deep=True
            )

            if local_container and local_container.properties:
                if not merged_containers[view_ref].properties:
                    merged_containers[view_ref].properties = local_container.properties
                else:
                    merged_containers[view_ref].properties.update(local_container.properties)

        return merged_containers

    def _is_ancestor_of_target(self, potential_ancestor: ViewReference, target_view_ref: ViewReference) -> bool:
        """Check if a view is an ancestor of the target view."""
        return potential_ancestor in self.local_resources.ancestors_by_view_reference.get(
            target_view_ref, set()
        ) or potential_ancestor in self.cdf_resources.ancestors_by_view_reference.get(target_view_ref, set())
