from collections import defaultdict
from itertools import chain, combinations
from typing import Literal, TypeAlias, TypeVar

import networkx as nx
from pyparsing import cached_property

from cognite.neat._data_model._constants import COGNITE_SPACES
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
from cognite.neat._utils.useful_types import ModusOperandi, T_Reference

# Type aliases for better readability
ViewsByReference: TypeAlias = dict[ViewReference, ViewRequest]
ContainersByReference: TypeAlias = dict[ContainerReference, ContainerRequest]
AncestorsByReference: TypeAlias = dict[ViewReference, set[ViewReference]]

ReverseToDirectMapping: TypeAlias = dict[
    tuple[ViewReference, str], tuple[ViewReference, ContainerDirectReference | ViewDirectReference]
]
ConnectionEndNodeTypes: TypeAlias = dict[tuple[ViewReference, str], ViewReference | None]


ResourceSource = Literal["auto", "merged", "cdf", "both"]

_NodeT = TypeVar("_NodeT", ContainerReference, ViewReference)

# Edge weight priority levels for _compute_requires_edge_weight.
# Uses lexicographic ordering via tuples: (priority, is_new_edge, neg_shared_views, neg_coverage, tie_breaker)
# Lower tuples are preferred. Python's tuple comparison handles priority naturally.
_PRIORITY_FORBIDDEN = 2  # Invalid edges (CDF sources, cycle-forming)
_PRIORITY_NEW_EDGE = 1  # Valid new edges that need to be added
_PRIORITY_FREE = 0  # Edges already satisfied by CDF constraints (no cost)


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
    def views_by_container(self) -> dict[ContainerReference, set[ViewReference]]:
        """Get a mapping from containers to the views that use them.

        Includes views from both the merged schema and all CDF views to capture
        container-view relationships across the entire CDF environment.
        Uses expanded views to include inherited properties.
        """

        # Include all unique views from merged and CDF
        views_by_container: dict[ContainerReference, set[ViewReference]] = defaultdict(set)

        # Include all unique views from merged and CDF
        all_view_refs = set(self.merged.views.keys()) | set(self.cdf.views.keys())

        for view_ref in all_view_refs:
            # Use expanded view to include inherited properties
            view = self.expand_view_properties(view_ref)
            if not view:
                continue

            for container in view.used_containers:
                views_by_container[container].add(view_ref)

        return dict(views_by_container)

    @cached_property
    def containers_by_view(self) -> dict[ViewReference, set[ContainerReference]]:
        """Get a mapping from views to the containers they use.

        Includes views from both the merged schema and all CDF views.
        Uses expanded views to include inherited properties.
        """
        containers_by_view: dict[ViewReference, set[ContainerReference]] = {}

        # Include all unique views from merged and CDF
        all_view_refs = set(self.merged.views.keys()) | set(self.cdf.views.keys())

        for view_ref in all_view_refs:
            # Use expanded view to include inherited properties
            view = self.expand_view_properties(view_ref)
            if view is not None:
                containers_by_view[view_ref] = view.used_containers

        return containers_by_view

    def find_views_mapping_to_containers(self, containers: list[ContainerReference]) -> set[ViewReference]:
        """Find views that map to all specified containers.

        That is, the intersection of views that use each of the specified containers.

        Args:
            containers: List of containers to check

        Returns:
            Set of views that contain all the specified containers

        Example:
            Given views V1, V2, V3 and containers C1, C2:
            - V1 uses containers {C1, C2}
            - V2 uses containers {C1}
            - V3 uses containers {C2}

            find_views_mapping_to_containers([C1, C2]) returns {V1}
            find_views_mapping_to_containers([C1]) returns {V1, V2}
            find_views_mapping_to_containers([C2]) returns {V1, V3}
        """
        if not containers:
            return set()

        view_sets = [self.views_by_container.get(c, set()) for c in containers]
        return set.intersection(*view_sets)

    @cached_property
    def implements_graph(self) -> nx.DiGraph:
        """Build a weighted directed graph of view implements.

        Nodes are ViewReferences, edges represent implements.
        An edge A → B means view A implements view B. Order of views in implements is used to set weight of an edge.

        Includes views from both merged schema and CDF
        """
        graph: nx.DiGraph = nx.DiGraph()

        for view_ref in self.cdf.views:
            graph.add_node(view_ref)
        for view_ref in self.merged.views:
            graph.add_node(view_ref)

        # Add edges for implements
        for view_ref in graph.nodes():
            view = self.select_view(view_ref)
            if not view or not view.implements:
                continue

            # Adding weight to preserve order of implements
            for i, implement in enumerate(view.implements):
                graph.add_edge(view_ref, implement, weight=i + 1)

        return graph

    @cached_property
    def implements_cycles(self) -> list[list[ViewReference]]:
        """Find all cycles in the implements graph.
        Returns:
            List of lists, where each list contains the ordered Views involved in forming the implements cycle.
        """

        return self.graph_cycles(self.implements_graph)

    @cached_property
    def requires_constraint_graph(self) -> nx.DiGraph:
        """Build a directed graph of container requires constraints.

        Nodes are ContainerReferences, edges represent requires constraints.
        An edge A → B means container A requires container B.

        Includes containers from both merged schema and CDF
        """
        graph: nx.DiGraph = nx.DiGraph()

        for container_ref in self.cdf.containers:
            graph.add_node(container_ref)
        for container_ref in self.merged.containers:
            graph.add_node(container_ref)

        # Add edges for requires constraints from all known containers
        for container_ref in graph.nodes():
            container = self.select_container(container_ref)
            if not container or not container.constraints:
                continue
            for constraint in container.constraints.values():
                if not isinstance(constraint, RequiresConstraintDefinition):
                    continue
                graph.add_edge(container_ref, constraint.require)

        return graph

    @staticmethod
    def forms_directed_path(nodes: set[_NodeT], graph: nx.DiGraph) -> bool:
        """Check if nodes form an uninterrupted directed path in the graph.

        Returns True if there exists a node that can reach all other nodes via
        directed edges in the graph.

        Args:
            nodes: Set of nodes to check
            graph: Directed graph containing the nodes

        Returns:
            True if nodes form a directed path (one node reaches all others)

        Example:
            Given nodes N1, N2, N3 with edges:
            - N1 -> N2
            - N2 -> N3

            forms_directed_path({N1, N2, N3}) returns True (N1 reaches all others)
            forms_directed_path({N2, N3}) returns True (N2 reaches N3)
            forms_directed_path({N1, N3}) returns False (N1 can't reach N3 without N2)
        """
        if len(nodes) <= 1:
            return True

        for candidate in nodes:
            others = nodes - {candidate}
            if others.issubset(nx.descendants(graph, candidate)):
                return True

        return False

    @cached_property
    def requires_constraint_cycles(self) -> list[list[ContainerReference]]:
        """Find all cycles in the requires constraint graph.
        Returns:
            List of lists, where each list contains the ordered containers involved in forming the requires cycle.
        """
        return self.graph_cycles(self.requires_constraint_graph)

    @staticmethod
    def graph_cycles(graph: nx.DiGraph) -> list[list[T_Reference]]:
        """Returns cycles in the graph otherwise empty list"""
        return [candidate for candidate in nx.simple_cycles(graph) if len(candidate) > 1]

    @cached_property
    def modifiable_containers(self) -> set[ContainerReference]:
        """Containers whose requires constraints can be modified.

        A container is modifiable if:
        - It's in the local/merged model (merged.containers)
        - It's NOT in a CDF built-in space (CDM, IDM, etc.)

        CDF built-in containers can't be modified because they're managed by Cognite.
        """
        return {container_ref for container_ref in self.merged.containers if container_ref.space not in COGNITE_SPACES}

    def _view_specificity_score(self, container: ContainerReference) -> tuple[int, int, str]:
        """Compute how view-specific a container is (lower = more specific = better outermost).

        Used to find the "outermost" container in a view - the one that should require all others.
        Returns: (view_count, cdf_descendants, external_id)
        """
        views = len(self.views_by_container.get(container, set()))
        descendants = len(self._immutable_descendants.get(container, set()))
        return (views, descendants, str(container))

    @cached_property
    def requires_mst(self) -> set[frozenset[ContainerReference]]:
        """Compute MST structure for container requires constraints.

        Builds a minimum spanning tree connecting containers that appear together
        in views. Returns undirected edges; orientation is determined per-view
        based on the view's outermost container.

        Returns:
            Set of frozensets, each containing exactly 2 ContainerReferences.
        """
        # Find all container pairs that need to be connected
        must_connect: set[frozenset[ContainerReference]] = set()
        for view_ref in self.merged.views:
            containers = self.containers_by_view.get(view_ref, set())
            if len(containers) >= 2:
                for c1, c2 in combinations(containers, 2):
                    must_connect.add(frozenset({c1, c2}))

        if not must_connect:
            return set()

        # Build undirected graph with edge weights
        G = nx.Graph()

        # Sort pairs for deterministic edge addition order (affects MST tie-breaking)
        forbidden_threshold = _PRIORITY_FORBIDDEN * 1e9
        for c1, c2 in sorted(must_connect, key=lambda p: tuple(sorted(str(c) for c in p))):
            w1 = self._compute_requires_edge_weight(c1, c2)
            w2 = self._compute_requires_edge_weight(c2, c1)
            # Skip if both directions are forbidden
            if w1 >= forbidden_threshold and w2 >= forbidden_threshold:
                continue
            G.add_edge(c1, c2, weight=min(w1, w2))

        # Compute MST for each connected component
        mst_edges: set[frozenset[ContainerReference]] = set()
        for component in nx.connected_components(G):
            if len(component) < 2:
                continue
            subgraph = G.subgraph(component)
            mst = nx.minimum_spanning_tree(subgraph, weight="weight")
            for c1, c2 in mst.edges():
                mst_edges.add(frozenset({c1, c2}))

        return mst_edges

    def get_requires_changes_for_view(
        self, view: ViewReference
    ) -> tuple[
        list[tuple[ContainerReference, ContainerReference]], list[tuple[ContainerReference, ContainerReference]]
    ]:
        """Get requires constraint changes for a view.

        Args:
            view: The view to get recommendations for.

        Returns:
            Tuple of (to_add, to_remove):
            - to_add: Edges to add for optimal structure
            - to_remove: Existing edges that should be removed (suboptimal)
        """
        containers = self.containers_by_view.get(view, set())
        modifiable_in_view = [c for c in containers if c in self.modifiable_containers]
        if not modifiable_in_view:
            return ([], [])

        # Get MST edges relevant to this view
        # An edge is relevant if BOTH endpoints are in the view (directly or via CDF coverage)
        relevant_mst_edges: set[frozenset[ContainerReference]] = set()
        for edge in self.requires_mst:
            c1, c2 = sorted(edge, key=str)  # Deterministic unpacking
            # Check if each endpoint is "in" the view (directly or transitively covers view containers)
            c1_coverage = self._immutable_descendants.get(c1, set()) | {c1}
            c2_coverage = self._immutable_descendants.get(c2, set()) | {c2}
            c1_relevant = bool(c1_coverage & containers)
            c2_relevant = bool(c2_coverage & containers)

            # Both endpoints must be relevant to the view
            if c1_relevant and c2_relevant:
                relevant_mst_edges.add(edge)

        # Orient edges from view's outermost container (modifiable must be source)
        view_outermost = min(modifiable_in_view, key=self._view_specificity_score)
        oriented_edges = self._orient_mst_edges_for_view(relevant_mst_edges, view_outermost, containers)

        # Get existing edges from modifiable containers in this view
        existing_edges: set[tuple[ContainerReference, ContainerReference]] = set()
        for src in modifiable_in_view:
            for dst in self.requires_constraint_graph.successors(src):
                existing_edges.add((src, dst))

        # Compute diff
        to_add = oriented_edges - existing_edges
        to_remove = existing_edges - oriented_edges

        # Sort for deterministic output
        sorted_add = sorted(to_add, key=lambda x: (str(x[0]), str(x[1])))
        sorted_remove = sorted(to_remove, key=lambda x: (str(x[0]), str(x[1])))

        return (sorted_add, sorted_remove)

    def _orient_mst_edges_for_view(
        self,
        mst_edges: set[frozenset[ContainerReference]],
        outermost: ContainerReference,
        containers: set[ContainerReference],
    ) -> set[tuple[ContainerReference, ContainerReference]]:
        """Orient MST edges for a view, ensuring the view-specific container can reach all others.

        Args:
            mst_edges: Undirected MST edges to orient
            outermost: The view-specific container (lowest _view_specificity_score)
            containers: All containers in this view
        """
        if not mst_edges:
            return set()

        # Build undirected graph and use nx.bfs_edges for traversal
        undirected = nx.Graph(tuple(edge) for edge in mst_edges)

        # Guard: if outermost has no MST edges (all were forbidden), skip BFS
        if outermost not in undirected:
            return set()

        oriented: set[tuple[ContainerReference, ContainerReference]] = set()

        for parent, child in nx.bfs_edges(undirected, outermost):
            # Orient: modifiable container must be source
            if parent in self.modifiable_containers:
                oriented.add((parent, child))
            elif child in self.modifiable_containers:
                oriented.add((child, parent))  # Flip when parent is CDF

        # Add direct edges for any containers unreachable due to CDF flips
        reach_graph = nx.DiGraph(oriented)
        reach_graph.add_edges_from(self.immutable_requires_constraint_graph.edges())
        reachable = nx.descendants(reach_graph, outermost) | {outermost}

        for container in containers - reachable:
            # Only add if it won't create a cycle with immutable constraints
            if outermost not in self._immutable_descendants.get(container, set()):
                oriented.add((outermost, container))

        return oriented

    @cached_property
    def immutable_requires_constraint_graph(self) -> nx.DiGraph:
        """Build a graph of requires constraints from non-modifiable containers.

        A container is non-modifiable if it's in a CDF built-in space (managed by Cognite)
        or not in the local/merged model. This graph represents constraints we cannot change.

        Containers without edges here get empty descendants via _immutable_descendants.get().
        """
        graph: nx.DiGraph = nx.DiGraph()
        for src, dst in self.requires_constraint_graph.edges():
            if src not in self.modifiable_containers:
                graph.add_edge(src, dst)

        return graph

    @cached_property
    def _immutable_descendants(self) -> dict[ContainerReference, set[ContainerReference]]:
        """Pre-compute descendants in immutable_requires_constraint_graph for all containers.

        This avoids repeated nx.descendants() calls which are O(V+E) each.

        Note: Only containers with edges in immutable_requires_constraint_graph are keys.
        Use .get(container, set()) to handle containers without immutable edges.
        """
        return {
            c: nx.descendants(self.immutable_requires_constraint_graph, c)
            for c in self.immutable_requires_constraint_graph.nodes()
        }

    def _compute_requires_edge_weight(self, src: ContainerReference, dst: ContainerReference) -> float:
        """Compute the weight/cost of connecting src and dst in the requires graph.

        Uses lexicographic priority encoded as a float:
        - Priority 0 (free): 0.0 - edges already satisfied by CDF
        - Priority 1 (new): 1.0 to 1.99 - new edges, with tie-breakers
        - Priority 2 (forbidden): 1e9 - invalid edges

        Tie-breakers for new edges (lower = better):
        - More shared views between src and dst
        - More CDF descendants on dst (transitive coverage)

        Args:
            src: Source container (the one that would "require")
            dst: Target container (the one being required)

        Returns:
            Float weight (lower = better).
        """
        # Priority 2: Forbidden - CDF built-in containers cannot be modified
        if src.space in COGNITE_SPACES:
            return float(_PRIORITY_FORBIDDEN) * 1e9

        # Priority 2: Forbidden - would create a cycle with immutable CDF constraints
        if src in self._immutable_descendants.get(dst, set()):
            return float(_PRIORITY_FORBIDDEN) * 1e9

        # Priority 0: Free - src can reach dst via immutable constraints
        if dst in self._immutable_descendants.get(src, set()):
            return float(_PRIORITY_FREE)

        # Priority 1: New edge needed - compute tie-breakers
        shared_views = len(self.views_by_container.get(src, set()) & self.views_by_container.get(dst, set()))
        coverage = len(self._immutable_descendants.get(dst, set()))

        # Encode tie-breakers: base 1.0, subtract small amounts for better edges
        # More shared views = lower weight (better)
        # More coverage = lower weight (better)
        # Cap contributions to stay in [1.0, 2.0) range
        shared_bonus = min(shared_views * 0.01, 0.1)  # Max 0.1 from 10+ shared views
        coverage_bonus = min(coverage * 0.01, 0.1)  # Max 0.1 from 10+ descendants

        return 1.0 + 0.5 - shared_bonus - coverage_bonus  # Range: [1.3, 1.5]
