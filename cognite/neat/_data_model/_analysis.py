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

    def find_views_with_both_containers(
        self, container_a: ContainerReference, container_b: ContainerReference
    ) -> set[ViewReference]:
        """Find views that contain both containers.

        Args:
            container_a: First container
            container_b: Second container

        Returns:
            Set of views containing both containers
        """
        views_a = self.container_to_views.get(container_a, set())
        views_b = self.container_to_views.get(container_b, set())
        return views_a & views_b

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

        # Add edges for requires constraints (only if target container exists)
        for container_ref in self.merged.containers:
            container = self.select_container(container_ref)
            if not container or not container.constraints:
                continue
            for constraint in container.constraints.values():
                if isinstance(constraint, RequiresConstraintDefinition):
                    # Only add edge if the required container actually exists
                    if self.select_container(constraint.require):
                        graph.add_edge(container_ref, constraint.require)

        return graph

    def has_full_requires_hierarchy(self, containers: set[ContainerReference]) -> bool:
        """Check if there's a container that transitively requires all other containers in the set.

        For query performance optimization, we only need ONE container to require all others.
        This allows the hasData filter to use only that outermost container.

        Uses nx.descendants() to check reachability.

        Args:
            containers: Set of containers to check

        Returns:
            True if at least one container requires all others (directly or transitively)
        """
        if len(containers) <= 1:
            return True

        for candidate in containers:
            others = containers - {candidate}
            if others.issubset(nx.descendants(self.requires_graph, candidate)):
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
            # Sort for deterministic ordering (frozenset iteration order is not guaranteed)
            c1, c2 = sorted(pair, key=str)
            # Add both directions, let MST pick the best
            G.add_edge(c1, c2, weight=self._compute_requires_edge_weight(c1, c2))
            G.add_edge(c2, c1, weight=self._compute_requires_edge_weight(c2, c1))

        # Existing requires get weight 0 (free to keep)
        for src in all_containers:
            for dst in self.requires_graph.successors(src):
                if dst in all_containers and G.has_edge(src, dst):
                    G[src][dst]["weight"] = 0.0

        # Step 4: Find minimum spanning arborescence
        # Arborescence: edges point AWAY from the root (root is the source).
        # We want outermost containers as roots, which the algorithm naturally selects
        # based on edge weights (outermost containers have more descendants coverage).
        try:
            arborescence = nx.minimum_spanning_arborescence(G, attr="weight")
        except nx.NetworkXException:
            # Graph may be disconnected - try to find forest of arborescences
            arborescence = nx.DiGraph()
            for component in nx.weakly_connected_components(G):
                if len(component) < 2:
                    continue
                subgraph = G.subgraph(component).copy()
                try:
                    sub_arb = nx.minimum_spanning_arborescence(subgraph, attr="weight")
                    arborescence = nx.compose(arborescence, sub_arb)
                except nx.NetworkXException:
                    continue

        # Step 5: Return only NEW edges where source is a user container
        # (users cannot modify CDF built-in containers, so those sources are not actionable)
        return {
            (src, dst)
            for src, dst in arborescence.edges()
            if dst not in set(self.requires_graph.successors(src)) and src.space not in CDF_BUILTIN_SPACES
        }

    def get_missing_requires_for_view(
        self, containers_in_view: set[ContainerReference]
    ) -> list[tuple[ContainerReference, ContainerReference]]:
        """Get the missing requires constraints for a specific view.

        Uses the globally optimal MST-based recommendations and filters to those
        relevant to this view. The global MST ensures consistency across views
        (e.g., "Tag → CogniteAsset" is recommended for all views containing Tag).

        Args:
            containers_in_view: Set of containers in the view being validated.

        Returns:
            List of (source, target) tuples representing requires constraints to add.
        """
        if len(containers_in_view) < 2:
            return []

        if self.has_full_requires_hierarchy(containers_in_view):
            return []

        user_containers = [c for c in containers_in_view if c.space not in CDF_BUILTIN_SPACES]
        if not user_containers:
            return []

        # Build a working graph: existing requires + relevant MST recommendations
        work_graph = self.requires_graph.copy()
        all_recs: list[tuple[ContainerReference, ContainerReference]] = []
        mst_connected_pairs = {frozenset({src, dst}) for src, dst in self.optimal_requires_tree}

        # Outermost = most specific container (appears in fewest views).
        # Tiebreaker 1: fewer ancestors (containers that require this one) = at top of hierarchy.
        # Tiebreaker 2: fewer descendants = less existing coverage = better root candidate.
        outermost = min(
            user_containers,
            key=lambda c: (
                len(self.container_to_views.get(c, set())),
                len(nx.ancestors(self.requires_graph, c)) if self.requires_graph.has_node(c) else 0,
                len(nx.descendants(self.requires_graph, c)) if self.requires_graph.has_node(c) else 0,
                str(c),  # Final tiebreaker for determinism
            ),
        )

        # Step 1: Add relevant MST recommendations
        # Include recs where src is a user container in this view, and either:
        # - dst is also in the view, OR
        # - dst's transitive chain covers uncovered containers in the view
        covered = (nx.descendants(work_graph, outermost) if work_graph.has_node(outermost) else set()) | {outermost}
        uncovered = containers_in_view - covered

        for src, dst in self.optimal_requires_tree:
            if src not in user_containers:
                continue

            # Skip if this would create a cycle
            if self.requires_graph.has_node(dst) and src in nx.descendants(self.requires_graph, dst):
                continue

            # Include if dst is in view
            if dst in containers_in_view:
                work_graph.add_edge(src, dst)
                all_recs.append((src, dst))
                continue

            # Include if dst's transitive chain covers uncovered containers
            dst_coverage = nx.descendants(self.requires_graph, dst) if self.requires_graph.has_node(dst) else set()
            if dst_coverage & uncovered:
                work_graph.add_edge(src, dst)
                all_recs.append((src, dst))
                covered = nx.descendants(work_graph, outermost) | {outermost}
                uncovered = containers_in_view - covered

        # Step 2: Add local edges from outermost to remaining uncovered containers

        while uncovered:
            user_uncovered = [c for c in uncovered if c.space not in CDF_BUILTIN_SPACES]
            candidates = user_uncovered if user_uncovered else list(uncovered)

            best_target = max(
                candidates,
                key=lambda c: len((nx.descendants(work_graph, c) if work_graph.has_node(c) else set()) & uncovered),
                default=None,
            )
            if best_target is None:
                break

            # Skip if MST already has an edge between these (in either direction)
            if frozenset({outermost, best_target}) in mst_connected_pairs:
                uncovered.remove(best_target)
                continue

            # Skip if adding this edge would create a cycle (best_target already requires outermost)
            if self.requires_graph.has_node(best_target) and outermost in nx.descendants(
                self.requires_graph, best_target
            ):
                uncovered.remove(best_target)
                continue

            work_graph.add_edge(outermost, best_target)
            all_recs.append((outermost, best_target))
            covered = nx.descendants(work_graph, outermost) | {outermost}
            uncovered = containers_in_view - covered

        # Step 3: Prune redundant recommendations
        # Build graph with all recs, then check each: is dst reachable without this edge?
        needed_recs: list[tuple[ContainerReference, ContainerReference]] = []
        for src, dst in all_recs:
            # Already exists in original graph?
            if dst in nx.descendants(self.requires_graph, src):
                continue

            # Temporarily remove this edge and check reachability via other recs
            work_graph.remove_edge(src, dst)
            is_redundant = (
                work_graph.has_node(src) and work_graph.has_node(dst) and dst in nx.descendants(work_graph, src)
            )
            work_graph.add_edge(src, dst)  # Restore for next iteration

            if not is_redundant:
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
        if not src_is_user:
            # CDF built-in container as source - users cannot modify these, so effectively forbidden
            base_weight += 1e9
        else:
            # User container as source - this is the actionable case
            base_weight -= 0.1

        # Factor 3: Existing transitivity - leverage existing chains
        if src in nx.descendants(self.requires_graph, dst):
            # dst already requires src, so src->dst would create a cycle - effectively forbidden
            base_weight += 1e9
        elif dst in nx.descendants(self.requires_graph, src):
            # src already transitively requires dst, this edge is redundant but cheap
            base_weight = 0.01

        # Factor 4: Strongly prefer targets that already have requires (leverage existing chains)
        # This is the key factor for choosing intermediate nodes over leaf nodes
        # (e.g., Tag → Asset over Tag → Describable when Asset requires Describable)
        dst_coverage = len(nx.descendants(self.requires_graph, dst))
        src_coverage = len(nx.descendants(self.requires_graph, src))

        # Prefer edges TO containers with more transitive coverage
        coverage_bonus = min(dst_coverage * 0.25, 0.6)
        base_weight -= coverage_bonus

        # Prefer edges TO containers with more coverage (intermediate nodes provide more value)
        # But penalize "leaf → root" edges where a leaf container requires a root container
        if dst_coverage > src_coverage:
            # Pointing TO a container with more coverage - generally good
            # But if src is a TRUE leaf (0 coverage), it's backwards to have it require a root
            if src_coverage == 0 and dst_coverage > 1:
                # Leaf → Root is backwards (e.g., Describable → Compressor)
                base_weight += dst_coverage * 0.1
            else:
                # Normal case: specific → intermediate (e.g., Parent → Middle, Tag → Asset)
                base_weight -= 0.15
        elif dst_coverage < src_coverage:
            # Pointing TO a container with less coverage - backwards
            base_weight += 0.2

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

        # Containers that transitively require dst
        containers_requiring_dst = (
            nx.ancestors(self.requires_graph, dst) if self.requires_graph.has_node(dst) else set()
        )

        affected: set[ViewReference] = set()
        for view_ref in src_views:
            if view_ref == exclude_view:
                continue
            view_containers = self.view_to_containers.get(view_ref, set())

            # dst is covered if: dst is in view OR any container in view already requires dst
            dst_is_covered = dst in view_containers or bool(containers_requiring_dst & view_containers)

            if not dst_is_covered:
                affected.add(view_ref)

        return affected
