import math
from collections import defaultdict
from collections.abc import Iterable
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
        containers_by_view: dict[ViewReference, set[ContainerReference]] = defaultdict(set)

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
        for container_ref in list(graph.nodes()):
            container = self.select_container(container_ref)
            if not container or not container.constraints:
                continue
            for constraint in container.constraints.values():
                if not isinstance(constraint, RequiresConstraintDefinition):
                    continue
                graph.add_edge(container_ref, constraint.require)

        return graph

    @cached_property
    def modifiable_containers(self) -> set[ContainerReference]:
        """Containers whose requires constraints can be modified in this session.

        A container is modifiable if:
        - It's in the currently loaded data model
        - It's NOT in a CDF built-in space (CDM, IDM, etc.)

        Non-modifiable containers include:
        - CDF built-in containers (CDM, IDM) - managed by Cognite
        - User containers in different data models - deployer skips them
        """
        return {container_ref for container_ref in self.merged.containers if container_ref.space not in COGNITE_SPACES}

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

        # Filter to nodes that are actually in the graph
        nodes_in_graph = {n for n in nodes if n in graph}
        if len(nodes_in_graph) < len(nodes):
            # Some nodes aren't in the graph, so we can't form a complete path
            return False

        for candidate in nodes_in_graph:
            others = nodes_in_graph - {candidate}
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

    def _is_solvable_with_edges(
        self,
        new_edges: Iterable[tuple[ContainerReference, ContainerReference]],
        containers: set[ContainerReference],
        base_graph: nx.DiGraph,
    ) -> bool:
        """Check if new_edges + base_graph edges allow a root to reach all containers."""
        graph = nx.DiGraph()
        graph.add_edges_from(new_edges)
        graph.add_edges_from(base_graph.edges())
        return self.forms_directed_path(containers, graph)

    @cached_property
    def _requires_mst_graph(self) -> nx.Graph:
        """Compute global MST graph with preferred_direction on each edge.

        We use a global MST (not per-view Steiner trees) because requires constraints
        are defined on containers, not views. A global tree ensures consistent edges
        across all views. The weight function favors edges that benefit multiple views.

        Each edge stores 'preferred_direction' based on the weight function, which can be
        used as a tie-breaker during orientation.
        """
        # Collect all container pairs that appear together in any view
        must_connect: set[frozenset[ContainerReference]] = set()
        for view_ref in self.merged.views:
            containers = self.containers_by_view.get(view_ref)
            if len(containers) < 2:
                continue
            for c1, c2 in combinations(containers, 2):
                must_connect.add(frozenset({c1, c2}))

        G = nx.Graph()
        # Sort pairs for deterministic edge addition order
        for c1, c2 in sorted(must_connect, key=lambda p: tuple(sorted(str(c) for c in p))):
            w1 = self._compute_requires_edge_weight(c1, c2)
            w2 = self._compute_requires_edge_weight(c2, c1)
            # Skip if both directions are forbidden (neither can be source)
            if math.isinf(w1) and math.isinf(w2):
                continue
            # Store minimum weight and preferred direction
            edge = (c1, c2) if w1 <= w2 else (c2, c1)
            G.add_edge(c1, c2, weight=min(w1, w2), preferred_direction=edge)

        return nx.minimum_spanning_tree(G, weight="weight")

    @cached_property
    def _mst_edges_by_view(self) -> dict[ViewReference, set[frozenset[ContainerReference]]]:
        """Map each view to the MST edges connecting its containers (Steiner tree).

        A view only needs edges that connect ITS containers, not all MST edges.
        This is the Steiner tree problem: find minimum edges to connect terminals.
        On a tree (MST), this is simply the union of paths between terminals.
        """
        if not self._requires_mst_graph:
            return {}

        result: dict[ViewReference, set[frozenset[ContainerReference]]] = defaultdict(set)

        for view_ref in self.merged.views:
            containers_in_mst = self.containers_by_view.get(view_ref).intersection(self._requires_mst_graph.nodes())
            if not containers_in_mst:
                continue

            # Steiner tree on a tree: BFS from any terminal, trace paths to others
            predecessors: dict[ContainerReference, ContainerReference] = dict(
                nx.bfs_predecessors(self._requires_mst_graph, next(iter(containers_in_mst)))
            )
            for target in containers_in_mst:
                node = target
                while node in predecessors:
                    result[view_ref].add(frozenset({node, predecessors[node]}))
                    node = predecessors[node]

        return result

    def _find_most_view_specific_container(self, containers: set[ContainerReference]) -> ContainerReference | None:
        """Find the most view-specific modifiable container to serve as root.

        Selection criteria (in priority order):
        1. Fewest views: Containers appearing in fewer views are more "view-specific"
           and make better roots since they won't affect as many other views.
        2. Has existing constraint: Prefer containers that already have outgoing
           constraints - this biases voting toward existing directions, minimizing changes.
        3. Alphabetical: Deterministic tie-breaker.

        Returns None if no modifiable containers.
        """
        modifiable_containers = containers.intersection(self.modifiable_containers)
        if not modifiable_containers:
            return None

        existing_edges = set(self.requires_constraint_graph.edges())
        most_view_specific: ContainerReference | None = None
        best_score: tuple[int, int, str] | None = None

        for container in modifiable_containers:
            view_count = len(self.views_by_container.get(container, set()))
            has_existing_constraint = any((container, other) in existing_edges for other in containers)
            score = (view_count, 0 if has_existing_constraint else 1, str(container))

            if best_score is None or score < best_score:
                most_view_specific, best_score = container, score

        return most_view_specific

    @cached_property
    def oriented_mst_edges(self) -> dict[frozenset[ContainerReference], tuple[ContainerReference, ContainerReference]]:
        """Orient MST edges by voting across views.

        Each view votes for edge orientations based on BFS from its most view-specific
        container (root). Views with only 1 modifiable container get 2x vote weight since
        that container MUST be root (no alternative). Tie-breakers: existing constraint,
        then preferred_direction from weight function.
        """
        edge_votes: dict[frozenset[ContainerReference], dict[tuple[ContainerReference, ContainerReference], int]] = (
            defaultdict(lambda: defaultdict(int))
        )

        for view, steiner_edges in self._mst_edges_by_view.items():
            containers = self.containers_by_view.get(view)
            view_specific_container = self._find_most_view_specific_container(containers)
            if not view_specific_container or not steiner_edges:
                continue

            # Views with only 1 modifiable container get 2x weight - they have NO choice
            # about which container is view_specific_container, so their vote is a hard constraint
            modifiable_in_view = containers.intersection(self.modifiable_containers)
            vote_weight = 2 if len(modifiable_in_view) == 1 else 1

            # BFS on Steiner subgraph: parent→child gives the direction this view wants
            steiner_nodes = {node for edge in steiner_edges for node in edge}
            steiner_subgraph = self._requires_mst_graph.subgraph(steiner_nodes)
            for parent, child in nx.bfs_edges(steiner_subgraph, view_specific_container):
                if parent in self.modifiable_containers:
                    edge_votes[frozenset({parent, child})][(parent, child)] += vote_weight

        # Map undirected edge → oriented direction
        oriented: dict[frozenset[ContainerReference], tuple[ContainerReference, ContainerReference]] = {}

        for c1, c2 in self._requires_mst_graph.edges():
            # Skip immutable-to-immutable edges
            if c1 not in self.modifiable_containers and c2 not in self.modifiable_containers:
                continue

            # Pick direction: most votes wins, preferred_direction breaks ties
            votes = edge_votes.get(frozenset({c1, c2}), {})
            c1_votes = votes.get((c1, c2), 0)
            c2_votes = votes.get((c2, c1), 0)

            if c1_votes > c2_votes:
                direction = (c1, c2)
            elif c2_votes > c1_votes:
                direction = (c2, c1)
            else:
                direction = self._requires_mst_graph[c1][c2].get("preferred_direction", (c1, c2))

            oriented[frozenset({c1, c2})] = direction

        return oriented

    def get_requires_changes_for_view(
        self, view: ViewReference
    ) -> tuple[
        list[tuple[ContainerReference, ContainerReference]], list[tuple[ContainerReference, ContainerReference]]
    ]:
        """Get requires constraint changes needed to optimize a view.

        Returns (to_add, to_remove) where:
        - to_add: New constraints needed (from global MST orientation)
        - to_remove: Existing constraints that are redundant or wrongly oriented

        Returns empty lists if the view would be unsolvable after changes, or if no changes are needed.
        """
        containers = self.containers_by_view.get(view)
        modifiable_containers_in_view = containers.intersection(self.modifiable_containers)
        if not modifiable_containers_in_view:
            return ([], [])

        # Get oriented edges for this view's Steiner tree
        steiner_edges = self._mst_edges_by_view.get(view, set())
        oriented_edges = {self.oriented_mst_edges[edge] for edge in steiner_edges if edge in self.oriented_mst_edges}

        # Current requires edges from modifiable containers in this view
        current_edges = {
            (src, dst) for src, dst in self.requires_constraint_graph.edges() if src in modifiable_containers_in_view
        }

        # To add: oriented Steiner edges (includes bridge containers outside view)
        to_add = {(src, dst) for src, dst in oriented_edges - current_edges if src in self.modifiable_containers}

        to_remove: set[tuple[ContainerReference, ContainerReference]] = set()
        mst_edges = {frozenset(e) for e in self._requires_mst_graph.edges()}

        for src, dst in current_edges:
            edge_undirected = frozenset[ContainerReference]({src, dst})
            edges_in_mst = edge_undirected in mst_edges
            mapped_by_external_views = self.find_views_mapping_to_containers([src, dst]) - set(self.merged.views.keys())

            # Edge is in MST but opposite direction → always remove (will be re-added flipped)
            if edges_in_mst and (src, dst) not in oriented_edges:
                to_remove.add((src, dst))
            # Edge not in MST → remove unless it serves external views
            elif not edges_in_mst and not mapped_by_external_views:
                to_remove.add((src, dst))

        # Check if the view would be solvable after applying ALL global recommendations
        # Use oriented_mst_edges as it includes edges from all views
        if not self._is_solvable_with_edges(
            self.oriented_mst_edges.values(), containers, self.immutable_requires_constraint_graph
        ):
            return ([], [])

        # Sort for deterministic output
        return (
            sorted(to_add, key=lambda x: (str(x[0]), str(x[1]))),
            sorted(to_remove, key=lambda x: (str(x[0]), str(x[1]))),
        )

    # ========================================================================
    # REQUIRES CONSTRAINT MST WEIGHT CONSTANTS
    # ========================================================================
    # Weight = TIER + sub_weight.
    #
    # WHY THIS ENCODING:
    # MST algorithm only support scalar weights, but we need a strict priority
    # hierarchy where USER→USER ALWAYS beats USER→EXTERNAL. By using a large
    # gap (1000) between tiers, sub-weights (max ~50) can never cause a lower
    # tier to beat a higher tier.
    #
    # Tiers (explicit priority order):
    #   - Tier 0 (FREE):          Immutable CDF constraints handle it
    #   - Tier 1 (USER→USER):     Both containers modifiable - always preferred
    #   - Tier 2 (USER→EXTERNAL): Target is CDF/CDM - only when needed
    #   - Tier ∞ (FORBIDDEN):     Invalid edge
    #
    # Sub-weights refine ordering WITHIN a tier (shared views, direction, etc).
    # ========================================================================

    # Tier base weights (gap of 1000 ensures tier always wins)
    _TIER_FREE = 0
    _TIER_USER_TO_USER = 1000
    _TIER_USER_TO_EXTERNAL = 2000
    _TIER_FORBIDDEN = math.inf

    # Sub-weight adjustments (applied within tier, max ~100)
    _BONUS_SHARED_VIEWS_PER = 5  # Per shared view (max 5 views → 25)
    _BONUS_SHARED_VIEWS_MAX = 25
    _BONUS_COVERAGE_PER = 5  # Per descendant via immutable edges (max 3 → 15)
    _BONUS_COVERAGE_MAX = 15
    _PENALTY_VIEW_COUNT = 10  # When src is in more views than dst

    # Tie-breaker for deterministic ordering
    _TIE_BREAKER_DIVISOR = 1e9

    def _compute_requires_edge_weight(self, src: ContainerReference, dst: ContainerReference) -> float:
        """Compute the weight/cost of adding edge src → dst.

        Returns TIER + sub_weight where tier dominates (gap of 1000).
        Sub-weights refine ordering within a tier based on shared views, direction, coverage.
        """
        if dst in self._immutable_descendants.get(src, set()):
            return self._TIER_FREE

        if src not in self.modifiable_containers or src in self._immutable_descendants.get(dst, set()):
            return self._TIER_FORBIDDEN

        src_views = self.views_by_container.get(src, set())
        dst_views = self.views_by_container.get(dst, set())

        # Sub-weight adjustments
        shared_bonus = min(len(src_views & dst_views) * self._BONUS_SHARED_VIEWS_PER, self._BONUS_SHARED_VIEWS_MAX)
        view_penalty = self._PENALTY_VIEW_COUNT if len(src_views) > len(dst_views) else 0

        # Deterministic tie-breaker
        edge_str = f"{src.space}:{src.external_id}->{dst.space}:{dst.external_id}"
        tie_breaker = sum(ord(c) for c in edge_str) / self._TIE_BREAKER_DIVISOR

        if dst in self.modifiable_containers:
            return self._TIER_USER_TO_USER - shared_bonus + view_penalty + tie_breaker

        # External target: add coverage bonus for well-connected CDF containers
        coverage_bonus = min(
            len(self._immutable_descendants.get(dst, set())) * self._BONUS_COVERAGE_PER, self._BONUS_COVERAGE_MAX
        )
        return self._TIER_USER_TO_EXTERNAL - shared_bonus - coverage_bonus + tie_breaker
