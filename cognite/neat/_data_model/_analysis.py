from itertools import chain
from typing import Literal, TypeAlias

from pyparsing import cached_property

from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms._constraints import RequiresConstraintDefinition
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


ResourceSource = Literal["auto", "merged", "cdf", "both"]


class ValidationResources:
    def __init__(
        self, modus_operandi: ModusOperandi, local: SchemaSnapshot, cdf: SchemaSnapshot, limits: SchemaLimits
    ) -> None:
        self._modus_operandi = modus_operandi
        self.limits = limits

        self.local = local
        self.cdf = cdf

        if self._modus_operandi == "additive":
            self.merged = self.local.merge(self.cdf)
        elif self._modus_operandi == "rebuild":
            self.merged = local.model_copy(deep=True)
        else:
            raise RuntimeError(f"ValidationResources: Unknown modus_operandi: {self._modus_operandi}. This is a bug!")

        # need this shortcut for easier access and also to avoid mypy to complains
        self.merged_data_model = self.merged.data_model[next(iter(self.merged.data_model.keys()))]

        # For caching of expanded views
        self._expanded_views_cache: dict[ViewReference, ViewRequest] = {}

    def select_view(
        self, view_ref: ViewReference, property_: str | None = None, source: ResourceSource = "auto"
    ) -> ViewRequest | None:
        """Select view definition based on source strategy and optionally filter by property.

        Selection prioritize merged view over CDF if both are available, as merged view represents the effective
        definition which will be a result when the local schema is deployed to CDF.


        Args:
            view_ref: The view to select
            property_: Optional property name to filter views that contain this property
            source: The source strategy to use, options are: "auto", "local", "cdf", "both", where "auto" means
                that the selection is driven by the modus_operandi of the validation resources.

        Returns:
            The selected ViewRequest or None if not found.
        """

        check_merged, check_cdf = self._resolve_resource_sources(view_ref, source)

        merged_view = self.merged.views.get(view_ref) if check_merged else None
        cdf_view = self.cdf.views.get(view_ref) if check_cdf else None

        if property_ is None:
            return merged_view or cdf_view

        # Filtering based on the property presence
        # Try views with the property first, then any available view where merged view is prioritized
        candidates = chain(
            (v for v in (merged_view, cdf_view) if v and v.properties and property_ in v.properties),
            (v for v in (merged_view, cdf_view) if v),
        )

        return next(candidates, None)

    def select_container(
        self, container_ref: ContainerReference, property_: str | None = None, source: ResourceSource = "auto"
    ) -> ContainerRequest | None:
        """Select container definition based on source strategy and optionally filter by property.

        Selection prioritize merged container over CDF if both are available, as merged container represents
        the effective definition which will be a result when the local schema is deployed to CDF.

        Args:
            container_ref: The container to select
            property_: Optional property name to filter containers that contain this property
            source: The source strategy to use, options are: "auto", "local", "cdf", "both", where "auto" means
                that the selection is driven by the modus_operandi of the validation resources.

        Returns:
            The selected ContainerRequest or None if not found.
        """

        check_merged, check_cdf = self._resolve_resource_sources(container_ref, source)

        merged_container = self.merged.containers.get(container_ref) if check_merged else None
        cdf_container = self.cdf.containers.get(container_ref) if check_cdf else None

        if property_ is None:
            return merged_container or cdf_container

        # Try containers with the property first, then any available container
        candidates = chain(
            (c for c in (merged_container, cdf_container) if c and c.properties and property_ in c.properties),
            (c for c in (merged_container, cdf_container) if c),
        )

        return next(candidates, None)

    def _resolve_resource_sources(
        self, resource_ref: ViewReference | ContainerReference, source: ResourceSource
    ) -> tuple[bool, bool]:
        """
        Determine which resource sources (merged and/or CDF) to check based on the source parameter.

        Args:
            resource_ref: The resource reference to check (ViewReference or ContainerReference)
            source: The source strategy to use

        Returns:
            Tuple of (check_merged, check_cdf) booleans indicating which sources to check
        """
        if source == "auto":
            # Auto mode: driven by data modeling modus (approach)
            # If elements is in the schema space, we check merged, else we check CDF

            in_schema_space = resource_ref.space == self.merged_data_model.space

            if self._modus_operandi == "additive":
                # In additive modus, schema space means local additions on top of CDF
                # always check CDF, while do not check merged if resource is not in schema space
                check_merged = in_schema_space
                check_cdf = True
            elif self._modus_operandi == "rebuild":
                # In rebuild modus, schema space means the full desired state is in local schema (i.e., merged)
                # you are not adding to CDF, but replacing it, so never check CDF for schema space resources
                check_merged = in_schema_space
                check_cdf = not in_schema_space
            else:
                raise RuntimeError(
                    f"_resolve_resource_sources: Unknown modus_operandi: {self._modus_operandi}. This is a bug!"
                )

        elif source == "merged":
            check_merged = True
            check_cdf = False
        elif source == "cdf":
            check_merged = False
            check_cdf = True
        elif source == "both":
            check_merged = True
            check_cdf = True
        else:
            raise RuntimeError(f"_resolve_resource_sources: Unknown source: {source}. This is a bug!")

        return check_merged, check_cdf

    @cached_property
    def ancestors_by_view(self) -> dict[ViewReference, list[ViewReference]]:
        """
        Create a mapping of each view to its list of ancestors.

        Returns:
            Dictionary mapping each ViewReference to its list of ancestor ViewReferences
        """
        ancestors_mapping: dict[ViewReference, list[ViewReference]] = {}

        if not self.merged_data_model.views:
            return ancestors_mapping

        for view in self.merged_data_model.views:
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

    def is_ancestor(self, offspring: ViewReference, ancestor: ViewReference) -> bool:
        return ancestor in self.view_ancestors(offspring)

    def _expand_view(self, view_ref: ViewReference) -> ViewRequest | None:
        """Expand a view by including properties from its ancestors.

        Args:
            view_ref: The view to expand.

        Returns:
            ViewRequest with expanded properties, or None if view not found.
        """
        view = self.select_view(view_ref)

        if not view:
            return None

        # Create a deep copy to avoid mutating the original
        expanded_view = view.model_copy(deep=True)

        # Get all ancestor properties (oldest to newest)
        ancestor_refs = self.view_ancestors(view_ref)
        ancestor_properties: dict[str, ViewRequestProperty] = {}

        # Collect properties from ancestors, overriding with newer ancestors properties
        for ancestor_ref in reversed(ancestor_refs):
            ancestor = self.select_view(ancestor_ref)
            if ancestor and ancestor.properties:
                ancestor_properties.update(ancestor.properties)

        # Merge: ancestor properties first, then override with view's own properties
        if ancestor_properties:
            if not expanded_view.properties:
                expanded_view.properties = {}

            # Ancestor properties are base, view properties override
            expanded_view.properties = {**ancestor_properties, **expanded_view.properties}

        return expanded_view

    def expand_view_properties(self, view_ref: ViewReference) -> ViewRequest | None:
        """Get a mapping of view references to their corresponding properties, both directly defined and inherited
        from ancestor views through implements."""

        if view_ref not in self._expanded_views_cache:
            expanded_view = self._expand_view(view_ref)
            if expanded_view:
                self._expanded_views_cache[view_ref] = expanded_view

        return self._expanded_views_cache.get(view_ref)

    @cached_property
    def referenced_containers(self) -> set[ContainerReference]:
        """Get a set of all container references used by the views in the local data model."""

        referenced_containers: set[ContainerReference] = set()

        if not self.merged_data_model.views:
            return referenced_containers

        for view_ref in self.merged_data_model.views:
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

        if self.merged_data_model.views:
            for view_ref in self.merged_data_model.views:
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

        if self.merged_data_model.views:
            for view_ref in self.merged_data_model.views:
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

    @cached_property
    def container_to_views(self) -> dict[ContainerReference, set[ViewReference]]:
        """Get a mapping from containers to the views that use them."""
        container_to_views: dict[ContainerReference, set[ViewReference]] = {}

        for view_ref, view in self.merged.views.items():
            if not view.properties:
                continue
            for property_ in view.properties.values():
                if isinstance(property_, ViewCorePropertyRequest):
                    container = property_.container
                    if container not in container_to_views:
                        container_to_views[container] = set()
                    container_to_views[container].add(view_ref)

        return container_to_views

    @cached_property
    def view_to_containers(self) -> dict[ViewReference, set[ContainerReference]]:
        """Get a mapping from views to the containers they use."""
        return {view_ref: view.used_containers for view_ref, view in self.merged.views.items() if view.used_containers}

    def containers_are_mapped_together(self, container_a: ContainerReference, container_b: ContainerReference) -> bool:
        """Check if two containers are mapped together in any view at least once.

        Args:
            container_a: First container reference
            container_b: Second container reference

        Returns:
            True if the containers are mapped together in at least one view
        """
        views_with_a = self.container_to_views.get(container_a, set())
        views_with_b = self.container_to_views.get(container_b, set())
        return bool(views_with_a & views_with_b)

    # =========================================================================
    # Container Requires Constraint Methods
    # =========================================================================

    def get_direct_required_containers(self, container_ref: ContainerReference) -> set[ContainerReference]:
        """Get all containers that a container directly requires.

        Uses merged containers for lookup.
        """
        container = self.merged.containers.get(container_ref)
        if not container or not container.constraints:
            return set()

        required: set[ContainerReference] = set()
        for constraint in container.constraints.values():
            if isinstance(constraint, RequiresConstraintDefinition):
                required.add(constraint.require)
        return required

    def get_transitively_required_containers(
        self,
        container_ref: ContainerReference,
        visited: set[ContainerReference] | None = None,
    ) -> set[ContainerReference]:
        """Get all containers that a container requires (transitively).

        Uses merged containers for lookup.
        """
        if visited is None:
            visited = set()
        if container_ref in visited:
            return set()
        visited.add(container_ref)

        direct_required = self.get_direct_required_containers(container_ref)
        all_required = direct_required.copy()
        for req in direct_required:
            all_required.update(self.get_transitively_required_containers(req, visited))
        return all_required

    def find_container_pairs_without_hierarchy(
        self, containers: set[ContainerReference]
    ) -> list[tuple[ContainerReference, ContainerReference]]:
        """Find container pairs where neither requires the other (directly or transitively).

        Args:
            containers: Set of containers to check

        Returns:
            List of (container_a, container_b) pairs with no requires relationship
        """
        containers_list = list(containers)
        missing_hierarchy: list[tuple[ContainerReference, ContainerReference]] = []

        for i, container_a in enumerate(containers_list):
            transitively_required_by_a = self.get_transitively_required_containers(container_a)

            for container_b in containers_list[i + 1 :]:
                transitively_required_by_b = self.get_transitively_required_containers(container_b)

                a_requires_b = container_b in transitively_required_by_a
                b_requires_a = container_a in transitively_required_by_b

                if not a_requires_b and not b_requires_a:
                    missing_hierarchy.append((container_a, container_b))

        return missing_hierarchy

    def has_full_requires_hierarchy(self, containers: set[ContainerReference]) -> bool:
        """Check if there's a container that transitively requires all other containers in the set.

        For query performance optimization, we only need ONE container to require all others.
        This allows the hasData filter to use only that outermost container.

        Args:
            containers: Set of containers to check

        Returns:
            True if at least one container requires all others (directly or transitively)
        """
        if len(containers) <= 1:
            return True

        others = containers.copy()
        for candidate in containers:
            others.discard(candidate)
            transitively_required = self.get_transitively_required_containers(candidate)
            if others <= transitively_required:
                return True
            others.add(candidate)

        return False

    def find_unrequired_containers(self, containers: set[ContainerReference]) -> set[ContainerReference]:
        """Find containers that are not transitively required by any other container in the set.

        These are the candidates for the "outermost" container, i.e. containers that could require all other containers.

        Args:
            containers: Set of containers to check

        Returns:
            Set of containers not required by any other container in the set
        """
        uncovered: set[ContainerReference] = set()

        for candidate in containers:
            is_required_by_another = False
            for other in containers:
                if other == candidate:
                    continue
                if candidate in self.get_transitively_required_containers(other):
                    is_required_by_another = True
                    break
            if not is_required_by_another:
                uncovered.add(candidate)

        return uncovered

    def find_unmapped_required_containers(
        self, containers_in_scope: set[ContainerReference]
    ) -> dict[ContainerReference, set[ContainerReference]]:
        """Find which containers require other containers not in the given scope.

        Args:
            containers_in_scope: Set of containers to check (e.g., containers in a view)

        Returns:
            Dict mapping each container to the set of required containers not in scope
        """
        requiring_containers: dict[ContainerReference, set[ContainerReference]] = {}

        for container_ref in containers_in_scope:
            all_required = self.get_transitively_required_containers(container_ref)
            not_in_scope = all_required - containers_in_scope
            if not_in_scope:
                requiring_containers[container_ref] = not_in_scope

        return requiring_containers

    def find_requires_constraint_cycle(
        self,
        start: ContainerReference,
        current: ContainerReference,
        visited: set[ContainerReference] | None = None,
        path: list[ContainerReference] | None = None,
    ) -> list[ContainerReference] | None:
        """Find a cycle in requires constraints starting from 'start' through 'current'.

        Returns the cycle path if found, None otherwise.
        """
        if visited is None:
            visited = set()
        if path is None:
            path = []

        if current in visited:
            if start == current:
                return [*path, current]
            return None

        visited.add(current)
        path.append(current)

        for required in self.get_direct_required_containers(current):
            cycle = self.find_requires_constraint_cycle(start, required, visited, path)
            if cycle:
                return cycle

        path.pop()
        return None

    def is_transitively_required_by_any(
        self,
        container: ContainerReference,
        container_set: set[ContainerReference],
        exclude: ContainerReference | None = None,
    ) -> bool:
        """Check if container is transitively required by any container in the set.

        For example, if A requires B requires C, then C is "covered by" A (and B).

        Args:
            container: The container to check
            container_set: Set of containers that might transitively require the target
            exclude: Optionally exclude a specific container from consideration
        """
        for other in container_set:
            if exclude is not None and other == exclude:
                continue
            if container in self.get_transitively_required_containers(other):
                return True
        return False

    def find_minimal_requires_set(
        self,
        candidates: set[ContainerReference],
        already_covered_by: set[ContainerReference] | None = None,
    ) -> set[ContainerReference]:
        """Remove containers that are already transitively required by other containers in the set.

        For example, if candidates = {A, B, C} and A requires B, the result is {A, C}
        because B is already covered by A's requires constraint.

        Args:
            candidates: Set of candidate containers to reduce
            already_covered_by: Additional containers whose transitive requirements
                should also be excluded from the result
        """
        if already_covered_by is None:
            already_covered_by = set()

        minimal: set[ContainerReference] = set()
        for container in candidates:
            # Skip if already covered by the pre-existing set
            if self.is_transitively_required_by_any(container, already_covered_by):
                continue
            # Skip if covered by another container in the same candidates set
            if self.is_transitively_required_by_any(container, candidates, exclude=container):
                continue
            minimal.add(container)
        return minimal
