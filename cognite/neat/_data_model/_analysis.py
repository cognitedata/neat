from itertools import chain
from typing import Literal, TypeAlias

from pyparsing import cached_property

from cognite.neat._data_model.deployer.data_classes import SchemaSnapshot
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._data_types import DirectNodeRelation
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._references import (
    ContainerDirectReference,
    ContainerReference,
    ViewDirectReference,
    ViewReference,
)
from cognite.neat._data_model.models.dms._view_property import (
    EdgeProperty,
    ReverseDirectRelationProperty,
    ViewCorePropertyRequest,
    ViewRequestProperty,
)
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._utils.useful_types import ModusOperandi

# Type aliases for better readability
ViewsByReference: TypeAlias = dict[ViewReference, ViewRequest]
ContainersByReference: TypeAlias = dict[ContainerReference, ContainerRequest]
AncestorsByReference: TypeAlias = dict[ViewReference, set[ViewReference]]
ReverseToDirectMapping: TypeAlias = dict[
    tuple[ViewReference, str], tuple[ViewReference, ContainerDirectReference | ViewDirectReference]
]
ConnectionEndNodeTypes: TypeAlias = dict[tuple[ViewReference, str], ViewReference | None]


ResourceSource = Literal["auto", "local", "cdf", "both"]


class ValidationResources:
    def __init__(
        self, modus_operandi: ModusOperandi, local: SchemaSnapshot, cdf: SchemaSnapshot, limits: SchemaLimits
    ) -> None:
        self.local = local
        self.cdf = cdf
        self.limits = limits
        self._modus_operandi = modus_operandi

        # need this shortcut for easier access and also to avoid mypy to complain
        self.local_data_model = self.local.data_model[next(iter(self.local.data_model.keys()))]

        # Update local resources based on modus operandi
        self._update_local_resources()

    def _update_local_resources(self) -> None:
        """Updates local resource definition with CDF resources for validation based on modus operandi.

        In "rebuild" mode, local resources are considered complete and no updates are made.
        In "additive" mode:
            - Local data model is updated to include views from CDF data model.
            - Local views are updated to include properties and implements from CDF views.
            - Local containers are updated to include properties from CDF containers.
        """

        # Local schema is complete, it does not require any updates
        # as changes will replace existing schema in CDF
        if self._modus_operandi == "rebuild":
            return None

        # Local schema is partial, meaning we are adding to existing schema in CDF
        elif self._modus_operandi == "additive":
            self._update_local_data_model()
            self._update_local_views()
            self._update_local_containers()
        else:
            raise RuntimeError(f"_update_local_resources: Unknown modus: {self._modus_operandi}. This is a bug!")

    def _update_local_data_model(self) -> None:
        if cdf := self.cdf.data_model.get(self.local_data_model.as_reference()):
            if not cdf.views:
                return None

            for view in cdf.views:
                if view not in (self.local_data_model.views or []):
                    self.local_data_model.views = (self.local_data_model.views or []) + [view]

    def _update_local_views(self) -> None:
        # update local views with additional properties and implements from CDF views

        for view_ref, view in self.local.views.items():
            if cdf_view := self.cdf.views.get(view_ref):
                # update properties
                for prop_name, prop in cdf_view.properties.items():
                    if prop_name not in view.properties:
                        view.properties[prop_name] = prop

                # update implements
                if cdf_view.implements:
                    if not view.implements:
                        view.implements = cdf_view.implements
                    else:
                        for impl in cdf_view.implements:
                            if impl not in view.implements:
                                view.implements.append(impl)

        # as we have updated view references in local data model, we need to ensure that any new views
        # from CDF are also added to local views for validation
        if not self.local_data_model.views:
            return None

        for view_ref in self.local_data_model.views:
            if view_ref not in self.local.views:
                if cdf_view := self.cdf.views.get(view_ref):
                    self.local.views[view_ref] = cdf_view

    def _update_local_containers(self) -> None:
        # update local containers definitions with additional properties from CDF containers
        for container_ref, container in self.local.containers.items():
            if cdf_container := self.cdf.containers.get(container_ref):
                for prop_name, prop in cdf_container.properties.items():
                    if prop_name not in container.properties:
                        container.properties[prop_name] = prop

        for view in self.local.views.values():
            if not view.properties:
                continue

            for property_ in view.properties.values():
                if not isinstance(property_, ViewCorePropertyRequest):
                    continue

                container_ref = property_.container
                # already updated in previous loop
                if container_ref in self.local.containers:
                    continue

                if cdf_container := self.cdf.containers.get(container_ref):
                    self.local.containers[container_ref] = cdf_container

    def select_view(
        self, view_ref: ViewReference, property_: str | None = None, source: ResourceSource = "auto"
    ) -> ViewRequest | None:
        check_local, check_cdf = self._resolve_resource_sources(view_ref, source)

        local_view = self.local.views.get(view_ref) if check_local else None
        cdf_view = self.cdf.views.get(view_ref) if check_cdf else None

        if property_ is None:
            return local_view or cdf_view

        # Try views with the property first, then any available view
        candidates = chain(
            (v for v in (local_view, cdf_view) if v and v.properties and property_ in v.properties),
            (v for v in (local_view, cdf_view) if v),
        )

        return next(candidates, None)

    def select_container(
        self, container_ref: ContainerReference, property_: str | None = None, source: ResourceSource = "auto"
    ) -> ContainerRequest | None:
        check_local, check_cdf = self._resolve_resource_sources(container_ref, source)

        local_container = self.local.containers.get(container_ref) if check_local else None
        cdf_container = self.cdf.containers.get(container_ref) if check_cdf else None

        if property_ is None:
            return local_container or cdf_container

        # Try containers with the property first, then any available container
        candidates = chain(
            (c for c in (local_container, cdf_container) if c and c.properties and property_ in c.properties),
            (c for c in (local_container, cdf_container) if c),
        )

        return next(candidates, None)

    def _resolve_resource_sources(
        self, resource_ref: ViewReference | ContainerReference, source: ResourceSource
    ) -> tuple[bool, bool]:
        """
        Determine which resource sources (local and/or CDF) to check based on the source parameter.

        Args:
            resource_ref: The resource reference to check (ViewReference or ContainerReference)
            source: The source strategy to use

        Returns:
            Tuple of (check_local, check_cdf) booleans indicating which sources to check
        """
        if source == "auto":
            # Auto mode: driven by modus_operandi
            # In "additive" mode or for resources outside local space, check both local and CDF
            # In "rebuild" mode for resources in local space, check only local
            check_local = True
            check_cdf = resource_ref.space != self.local_data_model.space or self._modus_operandi == "additive"
        elif source == "local":
            check_local = True
            check_cdf = False
        elif source == "cdf":
            check_local = False
            check_cdf = True
        elif source == "both":
            check_local = True
            check_cdf = True
        else:
            raise RuntimeError(f"_resolve_resource_sources: Unknown source: {source}. This is a bug!")

        return check_local, check_cdf

    @cached_property
    def ancestors_by_view(self) -> dict[ViewReference, list[ViewReference]]:
        """
        Create a mapping of each view to its list of ancestors.

        Returns:
            Dictionary mapping each ViewReference to its list of ancestor ViewReferences
        """
        ancestors_mapping: dict[ViewReference, list[ViewReference]] = {}

        if not self.local_data_model.views:
            return ancestors_mapping

        for view in self.local_data_model.views:
            ancestors_mapping[view] = self.view_ancestors(view)
        return ancestors_mapping

    def view_ancestors(
        self, offspring: ViewReference, ancestors: list[ViewReference] | None = None, source: ResourceSource = "auto"
    ) -> list[ViewReference]:
        """
        Recursively find all ancestors of a given view by traversing the implements hierarchy.
        Handles branching to explore all possible ancestor paths.

        Args:
            offspring: The view to find ancestors for
            ancestors: Accumulated list of ancestors (used internally for recursion)

        Returns:
            List of all ancestor ViewReferences
        """
        if ancestors is None:
            ancestors = []

        # Determine which view definition to use based on space and modus operandi

        view_definition = self.select_view(view_ref=offspring, source=source)

        # Base case: no view definition or no implements
        if not view_definition or not view_definition.implements:
            return ancestors

        # Explore all parent branches
        for parent in view_definition.implements:
            if parent not in ancestors:
                ancestors.append(parent)
                # Recursively explore this branch
                self.view_ancestors(parent, ancestors)

        return ancestors

    def expand_view(self, view_ref: ViewReference, source: ResourceSource = "auto") -> ViewRequest:
        """Expands view properties to include also inherited properties from ancestor views.

        Args:
            view_ref: The view to expand
            source: The source strategy to use

        Returns:
            The expanded ViewRequest with all inherited properties.
        """
        view = self.select_view(view_ref=view_ref, source=source)
        if not view:
            raise ValueError(f"expand_view: View {view_ref!s} not found in the specified source(s).")

        copy = view.model_copy(deep=True)

        ancestors = self.view_ancestors(view_ref, source=source)
        # Start with properties from ancestor views
        for ancestor_ref in reversed(ancestors):
            ancestor_view = self.select_view(ancestor_ref, source=source)
            if ancestor_view and ancestor_view.properties:
                if copy.properties is None:
                    copy.properties = {}

                for prop_name, prop in ancestor_view.properties.items():
                    if prop_name not in copy.properties:
                        copy.properties[prop_name] = prop

        return copy

    def is_ancestor(self, offspring: ViewReference, ancestor: ViewReference) -> bool:
        return ancestor in self.ancestors_by_view.get(offspring, set())

    @cached_property
    def properties_by_view(self) -> dict[ViewReference, dict[str, ViewRequestProperty]]:
        """Get a mapping of view references to their corresponding properties, both directly defined and inherited
        from ancestor views through implements."""

        properties_mapping: dict[ViewReference, dict[str, ViewRequestProperty]] = {}

        if self.local_data_model.views:
            for view_ref in self.local_data_model.views:
                view = self.select_view(view_ref)
                # This should never happen, if it happens, it's a bug
                if not view:
                    raise RuntimeError(f"properties_by_view: View {view_ref!s} not found. This is a bug!")

                combined_properties: dict[str, ViewRequestProperty] = {}
                ancestors = self.ancestors_by_view.get(view_ref, [])
                # Start with properties from ancestor views
                for ancestor_ref in reversed(ancestors):
                    ancestor_view = self.select_view(ancestor_ref)
                    if ancestor_view:
                        combined_properties.update(ancestor_view.properties)

                # Finally, add properties from the current view, overriding any inherited ones
                if view.properties:
                    combined_properties.update(view.properties)

                properties_mapping[view_ref] = combined_properties

        return properties_mapping

    @cached_property
    def referenced_containers(self) -> set[ContainerReference]:
        """Get a set of all container references used by the views in the local data model."""

        referenced_containers: set[ContainerReference] = set()

        if not self.local_data_model.views:
            return referenced_containers

        for view_ref in self.local_data_model.views:
            view = self.select_view(view_ref)
            # This should never happen, if it happens, it's a bug
            if not view:
                raise RuntimeError(f"referenced_containers: View {view_ref!s} not found. This is a bug!")

            if not view.properties:
                continue
            for property_ in view.properties.values():
                if isinstance(property_, ViewCorePropertyRequest):
                    referenced_containers.add(property_.container)

        return referenced_containers

    @cached_property
    def reverse_to_direct_mapping(
        self,
    ) -> dict[tuple[ViewReference, str], tuple[ViewReference, ContainerDirectReference | ViewDirectReference]]:
        """Get a mapping of reverse direct relations to their corresponding source view and 'through' property."""

        bidirectional_connections: dict[
            tuple[ViewReference, str], tuple[ViewReference, ContainerDirectReference | ViewDirectReference]
        ] = {}

        if self.local_data_model.views:
            for view_ref in self.local_data_model.views:
                view = self.select_view(view_ref)

                # This should never happen, if it happens, it's a bug
                if not view:
                    raise RuntimeError(f"reverse_to_direct_mapping: View {view_ref!s} not found. This is a bug!")

                if not view.properties:
                    continue
                for prop_ref, property_ in view.properties.items():
                    # reverse direct relation
                    if isinstance(property_, ReverseDirectRelationProperty):
                        bidirectional_connections[(view_ref, prop_ref)] = (
                            property_.source,
                            property_.through,
                        )

        return bidirectional_connections

    @property
    def connection_end_node_types(self) -> dict[tuple[ViewReference, str], ViewReference | None]:
        """Get a mapping of view references to their corresponding ViewRequest objects."""

        connection_end_node_types: dict[tuple[ViewReference, str], ViewReference | None] = {}

        if self.local_data_model.views:
            for view_ref in self.local_data_model.views:
                view = self.select_view(view_ref)
                if not view:
                    raise RuntimeError(f"View {view_ref!s} not found. This is a bug!")

                if not view.properties:
                    continue

                for prop_ref, property_ in view.properties.items():
                    # direct relation
                    if isinstance(property_, ViewCorePropertyRequest):
                        # explicit set of end node type via 'source' which is View reference
                        if property_.source:
                            connection_end_node_types[(view_ref, prop_ref)] = property_.source

                        # implicit end node type via container property, without actual knowledge of end node type
                        elif (
                            (
                                container := self.select_container(
                                    property_.container, property_.container_property_identifier
                                )
                            )
                            and (property_.container_property_identifier in container.properties)
                            and (
                                isinstance(
                                    container.properties[property_.container_property_identifier].type,
                                    DirectNodeRelation,
                                )
                            )
                        ):
                            connection_end_node_types[(view_ref, prop_ref)] = None

                    # reverse direct relation
                    elif isinstance(property_, ReverseDirectRelationProperty) and property_.source:
                        connection_end_node_types[(view_ref, prop_ref)] = property_.source

                    # edge property
                    elif isinstance(property_, EdgeProperty) and property_.source:
                        connection_end_node_types[(view_ref, prop_ref)] = property_.source

        return connection_end_node_types
