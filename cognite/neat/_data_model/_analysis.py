from itertools import chain
from typing import Literal, TypeAlias

import networkx as nx
from pyparsing import cached_property

from cognite.neat._data_model._constants import CDF_BUILTIN_SPACES
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
        """Get a mapping from containers to the views that use them.

        Includes views from both the merged schema and all CDF views to capture
        container-view relationships across the entire CDF environment.
        Uses expanded views to include inherited properties.
        """
        container_to_views: dict[ContainerReference, set[ViewReference]] = {}

        # Include all unique views from merged and CDF
        all_view_refs = set(self.merged.views.keys()) | set(self.cdf.views.keys())

        for view_ref in all_view_refs:
            # Use expanded view to include inherited properties
            view = self.expand_view_properties(view_ref)
            if not view:
                continue
            for container in view.used_containers:
                if container not in container_to_views:
                    container_to_views[container] = set()
                container_to_views[container].add(view_ref)

        return container_to_views

    @cached_property
    def view_to_containers(self) -> dict[ViewReference, set[ContainerReference]]:
        """Get a mapping from views to the containers they use.

        Includes views from both the merged schema and all CDF views.
        Uses expanded views to include inherited properties.
        """
        view_to_containers: dict[ViewReference, set[ContainerReference]] = {}

        # Include all unique views from merged and CDF
        all_view_refs = set(self.merged.views.keys()) | set(self.cdf.views.keys())

        for view_ref in all_view_refs:
            # Use expanded view to include inherited properties
            view = self.expand_view_properties(view_ref)
            if view and view.used_containers:
                view_to_containers[view_ref] = view.used_containers

        return view_to_containers

    def are_containers_mapped_together(self, container_a: ContainerReference, container_b: ContainerReference) -> bool:
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
    # Container Requires Constraint Methods (using networkx for graph operations)
    # =========================================================================

    @cached_property
    def requires_graph(self) -> nx.DiGraph:
        """Build a directed graph of container requires constraints.

        Nodes are ContainerReferences, edges represent requires constraints.
        An edge A → B means container A requires container B.
        """
        graph: nx.DiGraph = nx.DiGraph()

        # Add all containers as nodes
        for container_ref in self.merged.containers:
            graph.add_node(container_ref)

        # Add edges for requires constraints
        for container_ref in self.merged.containers:
            container = self.select_container(container_ref)
            if not container or not container.constraints:
                continue
            for constraint in container.constraints.values():
                if isinstance(constraint, RequiresConstraintDefinition):
                    graph.add_edge(container_ref, constraint.require)

        return graph

    def get_direct_required_containers(self, container_ref: ContainerReference) -> set[ContainerReference]:
        """Get all containers that a container directly requires."""
        if container_ref not in self.requires_graph:
            return set()
        return set(self.requires_graph.successors(container_ref))

    def get_transitively_required_containers(self, container_ref: ContainerReference) -> frozenset[ContainerReference]:
        """Get all containers that a container requires (transitively).

        Uses networkx descendants() which handles cycles gracefully.
        """
        if container_ref not in self.requires_graph:
            return frozenset()
        return frozenset(nx.descendants(self.requires_graph, container_ref))

    def has_full_requires_hierarchy(self, containers: set[ContainerReference]) -> bool:
        """Check if there's a container that transitively requires all other containers in the set.

        For query performance optimization, we only need ONE container to require all others.
        This allows the hasData filter to use only that outermost container.

        Uses nx.descendants() (via get_transitively_required_containers) to check reachability.

        Args:
            containers: Set of containers to check

        Returns:
            True if at least one container requires all others (directly or transitively)
        """
        if len(containers) <= 1:
            return True

        for candidate in containers:
            others = containers - {candidate}
            if others.issubset(self.get_transitively_required_containers(candidate)):
                return True

        return False

    @cached_property
    def requires_constraint_cycles(self) -> list[set[ContainerReference]]:
        """Find all cycles in the requires constraint graph using Tarjan's algorithm.

        Uses strongly connected components (SCC) to identify cycles efficiently.
        An SCC with more than one node indicates a cycle.

        Returns:
            List of sets, where each set contains the containers involved in a cycle.
        """
        sccs = nx.strongly_connected_components(self.requires_graph)
        # Only SCCs with more than one node represent cycles
        return [scc for scc in sccs if len(scc) > 1]

    @cached_property
    def optimal_requires_tree(self) -> set[tuple[ContainerReference, ContainerReference]]:
        """Compute the globally optimal set of requires constraints for the entire data model.

        This considers ALL containers that appear together in ANY view and finds the
        minimum set of NEW requires constraints that would complete all hierarchies
        optimally across the entire data model.

        Uses Minimum Spanning Arborescence (Edmonds' algorithm) on a graph where:
        - Nodes are all containers that appear in local views
        - Edges connect containers that appear together in any view
        - Edge weights favor: existing requires (free), shared views, user containers

        The result is cached and used for all per-view validation.

        Returns:
            Set of (source, target) tuples representing requires constraints to add.
            Each tuple means "source should require target".
        """
        # Step 1: Find all containers that appear in merged views
        all_containers: set[ContainerReference] = set()
        for view_ref in self.merged.views:
            containers = self.view_to_containers.get(view_ref, set())
            all_containers.update(containers)

        if len(all_containers) < 2:
            return set()

        # Step 2: Find which container pairs need to be connected
        # (containers that appear together in at least one view)
        must_connect: set[frozenset[ContainerReference]] = set()
        for view_ref in self.merged.views:
            containers = self.view_to_containers.get(view_ref, set())
            if len(containers) >= 2:
                # All pairs in this view must be connected (directly or transitively)
                for c1 in containers:
                    for c2 in containers:
                        if c1 != c2:
                            must_connect.add(frozenset({c1, c2}))

        if not must_connect:
            return set()

        # Step 3: Build directed graph with edge weights
        G = nx.DiGraph()
        for container in all_containers:
            G.add_node(container)

        # Add edges only between containers that must be connected
        for pair in must_connect:
            c1, c2 = tuple(pair)
            # Add both directions, let MST pick the best
            G.add_edge(c1, c2, weight=self._compute_requires_edge_weight(c1, c2))
            G.add_edge(c2, c1, weight=self._compute_requires_edge_weight(c2, c1))

        # Existing requires get weight 0 (free to keep)
        for src in all_containers:
            for dst in self.get_direct_required_containers(src):
                if dst in all_containers and G.has_edge(src, dst):
                    G[src][dst]["weight"] = 0.0

        # Step 4: Find minimum spanning arborescence
        # IMPORTANT: Arborescence edges point AWAY from the root.
        # We want user containers as roots (edges: user → CDF built-in).
        # To achieve this, we reverse the graph, find arborescence (edges point TO CDF),
        # then reverse the result back.
        G_reversed = G.reverse()

        try:
            arborescence_reversed = nx.minimum_spanning_arborescence(G_reversed, attr="weight")
            # Reverse edges back to get the correct direction
            arborescence = arborescence_reversed.reverse()
        except nx.NetworkXException:
            # Graph may be disconnected - try to find forest of arborescences
            arborescence = nx.DiGraph()
            for component in nx.weakly_connected_components(G):
                if len(component) < 2:
                    continue
                subgraph = G.subgraph(component).copy()
                subgraph_reversed = subgraph.reverse()
                try:
                    sub_arb_rev = nx.minimum_spanning_arborescence(subgraph_reversed, attr="weight")
                    sub_arb = sub_arb_rev.reverse()
                    arborescence = nx.compose(arborescence, sub_arb)
                except nx.NetworkXException:
                    continue

        # Step 5: Return only NEW edges where source is a user container
        # (users cannot modify CDF built-in containers, so those sources are not actionable)
        return {
            (src, dst)
            for src, dst in arborescence.edges()
            if dst not in self.get_direct_required_containers(src) and src.space not in CDF_BUILTIN_SPACES
        }

    def get_missing_requires_for_view(
        self, containers_in_view: set[ContainerReference]
    ) -> list[tuple[ContainerReference, ContainerReference]]:
        """Get the missing requires constraints for a specific view.

        Uses the globally optimal MST-based recommendations and filters to those
        relevant to this view. The global MST ensures consistency across views
        (e.g., "Tag → CogniteAsset" is recommended for all views containing Tag).

        For each view, we report global recommendations where:
        1. The source container is in this view (the constraint helps this view)
        2. The constraint is not already transitively satisfied

        Args:
            containers_in_view: Set of containers in the view being validated.

        Returns:
            List of (source, target) tuples representing requires constraints to add.
        """
        if len(containers_in_view) < 2:
            return []

        # Check if hierarchy is already complete for this view
        if self.has_full_requires_hierarchy(containers_in_view):
            return []

        # Get the globally optimal recommendations from MST
        global_recs = self.optimal_requires_tree

        # Filter to recommendations where the source is in this view
        # We include ALL global MST recommendations for containers in this view,
        # trusting the MST's global optimization. The redundancy pruning will
        # remove any that aren't actually needed.
        relevant_recs: list[tuple[ContainerReference, ContainerReference]] = []

        for src, dst in global_recs:
            if src not in containers_in_view:
                continue

            # Skip CDF containers as sources - users cannot modify them
            if src.space in CDF_BUILTIN_SPACES:
                continue

            relevant_recs.append((src, dst))

        # Step 1: Build simulated coverage after applying MST recommendations
        simulated_requires: dict[ContainerReference, set[ContainerReference]] = {}
        for c in containers_in_view:
            simulated_requires[c] = set(self.get_transitively_required_containers(c))

        # Apply MST recommendations to simulated coverage
        for src, dst in relevant_recs:
            if src in simulated_requires:
                simulated_requires[src].add(dst)
                simulated_requires[src].update(self.get_transitively_required_containers(dst))

        # Find user containers in this view (containers not in CDF built-in spaces)
        user_containers = [c for c in containers_in_view if c.space not in CDF_BUILTIN_SPACES]

        # Step 2: Add edges between user containers if hierarchy is still incomplete
        # (MST might not connect all user containers within this view)
        all_recs = list(relevant_recs)

        # Check if any user container covers all others
        hierarchy_complete = any(
            (simulated_requires.get(c, set()) | {c}) >= containers_in_view for c in user_containers
        )

        if not hierarchy_complete and user_containers:
            # Find the best outermost candidate (most coverage, fewest views = most specific)
            outermost = max(
                user_containers,
                key=lambda c: (
                    len((simulated_requires.get(c, set()) | {c}) & containers_in_view),
                    -len(self.container_to_views.get(c, set())),
                ),
            )
            covered = simulated_requires.get(outermost, set()) | {outermost}
            uncovered = containers_in_view - covered

            # Add edges from outermost to uncovered user containers
            # Prefer user containers as targets (they provide more transitive coverage)
            while uncovered:
                best_target = None
                best_coverage: set[ContainerReference] = set()

                # Prefer user containers as targets
                user_uncovered = [c for c in uncovered if c.space not in CDF_BUILTIN_SPACES]
                candidates = user_uncovered if user_uncovered else list(uncovered)

                for candidate in candidates:
                    # What would requiring this candidate cover?
                    candidate_sim_cov = simulated_requires.get(candidate, set()) | {candidate}
                    candidate_covers = candidate_sim_cov & uncovered
                    if len(candidate_covers) > len(best_coverage):
                        best_coverage = candidate_covers
                        best_target = candidate

                if best_target is None:
                    break

                all_recs.append((outermost, best_target))
                # Update simulated coverage
                simulated_requires[outermost].add(best_target)
                simulated_requires[outermost].update(self.get_transitively_required_containers(best_target))
                covered = simulated_requires.get(outermost, set()) | {outermost}
                uncovered = containers_in_view - covered

        # Step 3: Prune redundant recommendations using graph reachability
        # Build a temporary graph with existing edges + all recommendations
        # Then check if each recommendation is redundant (dst reachable without it)
        needed_recs: list[tuple[ContainerReference, ContainerReference]] = []

        for src, dst in all_recs:
            # Check existing transitive coverage (without any recommendations)
            existing_coverage = self.get_transitively_required_containers(src)
            if dst in existing_coverage:
                continue

            # Build graph with existing edges + OTHER recommendations
            temp_graph = self.requires_graph.copy()
            for other_src, other_dst in all_recs:
                if (other_src, other_dst) != (src, dst):
                    temp_graph.add_edge(other_src, other_dst)

            # Check if dst is reachable from src in this graph (without the current edge)
            if temp_graph.has_node(src) and temp_graph.has_node(dst):
                reachable = nx.descendants(temp_graph, src)
                if dst in reachable:
                    continue  # Redundant - covered by other recommendations

            needed_recs.append((src, dst))

        return sorted(needed_recs, key=lambda x: (str(x[0]), str(x[1])))

    def _compute_requires_edge_weight(self, src: ContainerReference, dst: ContainerReference) -> float:
        """Compute the weight/cost of adding a requires constraint from src to dst.

        Lower weight = more preferred edge. Weights are based on:
        1. Shared views: containers that appear together often are preferred
        2. User vs CDF: user containers are preferred over CDF built-in containers as sources
        3. Existing transitivity: if src already transitively requires dst, very cheap

        Args:
            src: Source container (the one that would "require")
            dst: Target container (the one being required)

        Returns:
            Edge weight (lower = better). Always positive.
        """
        base_weight = 1.0

        # Factor 1: Shared views - prefer containers that appear together more often
        src_views = self.container_to_views.get(src, set())
        dst_views = self.container_to_views.get(dst, set())
        # Only count views from merged schema (current model scope)
        merged_views = set(self.merged.views.keys())
        shared_views = len(src_views & dst_views & merged_views)
        # More shared views = lower weight (bonus of 0.05 per shared view, max 0.5)
        view_bonus = min(shared_views * 0.05, 0.5)
        base_weight -= view_bonus

        # Factor 2: User vs CDF built-in - user containers should require CDF containers, not vice versa
        src_is_user = src.space not in CDF_BUILTIN_SPACES
        dst_is_user = dst.space not in CDF_BUILTIN_SPACES

        if not src_is_user:
            # CDF built-in container as source - user CAN'T modify these!
            # This should almost never be recommended
            base_weight += 100.0
        elif src_is_user and not dst_is_user:
            # User container requiring CDF built-in - this is ideal
            base_weight -= 0.3
        elif src_is_user and dst_is_user:
            # User requiring user is fine
            base_weight -= 0.1

        # Factor 3: Existing transitivity - leverage existing chains
        if src in self.get_transitively_required_containers(dst):
            # dst already requires src, so src->dst would create a cycle - effectively forbidden
            base_weight += 1e9
        elif dst in self.get_transitively_required_containers(src):
            # src already transitively requires dst, this edge is redundant but cheap
            base_weight = 0.01

        # Factor 4: Transitive coverage - prefer targets that already require other containers
        # This makes Parent→Middle preferable to Parent→Leaf if Middle→Leaf exists
        dst_transitive_coverage = len(self.get_transitively_required_containers(dst))
        # More coverage = lower weight (bonus of 0.1 per transitively required container)
        coverage_bonus = min(dst_transitive_coverage * 0.1, 0.4)
        base_weight -= coverage_bonus

        return max(base_weight, 0.01)

    def find_views_affected_by_requires(
        self,
        src: ContainerReference,
        dst: ContainerReference,
        exclude_view: ViewReference | None = None,
    ) -> set[ViewReference]:
        """Find views where adding src → dst would affect ingestion.

        A view is affected if:
        - It contains src (so the new constraint applies)
        - It does NOT already have dst covered (either directly or via another container
          that already requires dst)

        Args:
            src: Source container that would get the new requires constraint
            dst: Target container that would be required
            exclude_view: Optional view to exclude from results (typically the current view)

        Returns:
            Set of views that would be affected by this constraint
        """
        src_views = self.container_to_views.get(src, set())

        affected: set[ViewReference] = set()
        for view_ref in src_views:
            if view_ref == exclude_view:
                continue
            view_containers = self.view_to_containers.get(view_ref, set())

            # Check if dst is already covered in this view:
            # 1. dst is directly in the view, OR
            # 2. Some container in the view already requires dst (transitively)
            dst_is_covered = dst in view_containers or any(
                dst in self.get_transitively_required_containers(c) for c in view_containers
            )

            if not dst_is_covered:
                affected.add(view_ref)

        return affected

    def find_views_with_both_containers(self, src: ContainerReference, dst: ContainerReference) -> set[ViewReference]:
        """Find views that contain both src and dst containers.

        These "superset" views can serve as ingestion points for views that only
        have src (and would be affected by adding src → dst).

        Args:
            src: Source container
            dst: Target container

        Returns:
            Set of views containing both containers
        """
        src_views = self.container_to_views.get(src, set())
        dst_views = self.container_to_views.get(dst, set())
        return src_views & dst_views
