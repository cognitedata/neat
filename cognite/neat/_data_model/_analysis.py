import math
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
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


class RequiresChangeStatus(Enum):
    """Status of requires constraint changes for a view."""

    OPTIMAL = "optimal"  # Already optimized, no changes needed
    CHANGES_AVAILABLE = "changes_available"  # Recommendations available
    UNSOLVABLE = "unsolvable"  # Structural issue - can't create connected hierarchy
    NO_MODIFIABLE_CONTAINERS = "no_modifiable_containers"  # All containers are immutable


@dataclass
class RequiresChangesForView:
    """Result of computing requires constraint changes for a view."""

    to_add: set[tuple[ContainerReference, ContainerReference]]
    to_remove: set[tuple[ContainerReference, ContainerReference]]
    status: RequiresChangeStatus


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
        for container_ref in list(graph.nodes()):
            container = self.select_container(container_ref)
            if not container or not container.constraints:
                continue
            for constraint_id, constraint in container.constraints.items():
                if not isinstance(constraint, RequiresConstraintDefinition):
                    continue
                is_auto = constraint_id.endswith("__auto")
                graph.add_edge(container_ref, constraint.require, is_auto=is_auto)

        return graph

    @cached_property
    def modifiable_containers(self) -> set[ContainerReference]:
        """Containers whose requires constraints can be modified in this session.

        A container is modifiable if:
        - It's NOT in a CDF built-in space (CDM, IDM, etc.)
        - It's a user container brought in through the loaded data model scope or view implements chain
        """
        return {container_ref for container_ref in self.merged.containers if container_ref.space not in COGNITE_SPACES}

    @cached_property
    def immutable_requires_constraint_graph(self) -> nx.DiGraph:
        """Subgraph of requires constraints from non-modifiable (CDM) containers.

        Used to check reachability via existing immutable constraints.
        """
        return nx.subgraph_view(
            self.requires_constraint_graph,
            filter_edge=lambda src, _: src not in self.modifiable_containers,
        )

    @cached_property
    def _fixed_constraint_graph(self) -> nx.DiGraph:
        """Graph of all fixed constraints (immutable + user-intentional).

        Both are "fixed" from the optimizer's perspective - existing paths that can't be changed.
        """
        G = nx.DiGraph()
        G.add_edges_from(self.immutable_requires_constraint_graph.edges())
        G.add_edges_from(self._user_intentional_constraints)
        return G

    @cached_property
    def _fixed_descendants(self) -> defaultdict[ContainerReference, set[ContainerReference]]:
        """Pre-compute descendants via fixed constraints. Missing keys return empty set."""
        result: defaultdict[ContainerReference, set[ContainerReference]] = defaultdict(set)
        for container in self._fixed_constraint_graph.nodes():
            result[container] = nx.descendants(self._fixed_constraint_graph, container)
        return result

    @cached_property
    def _existing_requires_edges(self) -> set[tuple[ContainerReference, ContainerReference]]:
        """Cached set of existing requires constraint edges."""
        return set(self.requires_constraint_graph.edges())

    @cached_property
    def _user_intentional_constraints(self) -> set[tuple[ContainerReference, ContainerReference]]:
        """Constraints that appear to be user-intentional and should not be auto-removed

        A constraint is user-intentional if:
        1. The constraint identifier does NOT have '__auto' postfix
        2. Neither src nor dst is part of a cycle (cyclic constraints are errors)

        These constraints are preserved even if they're not in the optimal structure, because
        they may be used for data integrity purposes.
        We DON'T consider manual-created constraints as user-intended if they form part of a cycle,
        because that indicates a problem with the data model where we likely can provide a better solution.
        """
        containers_in_cycles = {container for cycle in self.requires_constraint_cycles for container in cycle}

        return {
            (src, dst)
            for src, dst, data in self.requires_constraint_graph.edges(data=True)
            if not data.get("is_auto", False) and src not in containers_in_cycles and dst not in containers_in_cycles
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

    @cached_property
    def optimized_requires_constraint_graph(self) -> nx.DiGraph:
        """Target state of requires constraints after optimizing (MST + fixed constraints)."""
        graph = nx.DiGraph()
        graph.add_edges_from(self.oriented_mst_edges)
        graph.add_edges_from(self._fixed_constraint_graph.edges())
        return graph

    @cached_property
    def _requires_candidate_graph(self) -> nx.Graph:
        """Build weighted candidate graph for requires constraints.

        Contains all container pairs that appear together in any view, with:
        - weight: minimum directional weight (for MST computation)
        - preferred_direction: direction with lower weight (for tie-breaking)

        This graph is used to compute per-view MSTs.
        """
        G = nx.Graph()

        for view_ref in self.merged.views:
            containers = self.containers_by_view.get(view_ref)
            if len(containers) < 2:
                continue  # Need at least 2 containers to form a requires constraint

            # Sort for deterministic preferred_direction when weights are equal
            for src, dst in combinations(sorted(containers, key=str), 2):
                if G.has_edge(src, dst):
                    continue  # Already added from another view

                w1 = self._compute_requires_edge_weight(src, dst)
                w2 = self._compute_requires_edge_weight(dst, src)
                direction = (src, dst) if w1 <= w2 else (dst, src)
                weight = min(w1, w2)

                G.add_edge(src, dst, weight=weight, preferred_direction=direction)

        return G

    @cached_property
    def _mst_by_view(self) -> dict[ViewReference, nx.Graph]:
        """Compute per-view MST graphs.

        Each view gets its own MST over just its containers. This ensures:
        - No routing through containers not in the view
        - Each view gets exactly the edges it needs
        - Voting handles orientation conflicts between views

        Skips inherently unsolvable views (no immutable anchor + all modifiables are roots).
        """
        if not self._requires_candidate_graph:
            return {}

        result: dict[ViewReference, nx.Graph] = {}

        for view_ref in self.merged.views:
            if view_ref in self._views_with_root_conflicts:
                continue

            containers = self.containers_by_view.get(view_ref)
            if len(containers) < 2:  # Need at least 2 containers to have a constraint
                continue
            if not containers.intersection(self.modifiable_containers):
                continue

            subgraph = self._requires_candidate_graph.subgraph(containers)
            if not nx.is_connected(subgraph):
                continue

            result[view_ref] = nx.minimum_spanning_tree(subgraph, weight="weight")

        return result

    @cached_property
    def _root_by_view(self) -> dict[ViewReference, ContainerReference]:
        """Map each view (with 2+ containers) to its most view-specific (root) container.

        Only includes views with 2+ containers since single-container views
        are trivially satisfied and don't need root direction.

        Selection criteria (in priority order):
        1. Fewest views: Containers appearing in fewer views are more "view-specific"
        2. Has existing constraint: Prefer containers with existing outgoing constraints
        3. Alphabetical: Deterministic tie-breaker
        """
        result: dict[ViewReference, ContainerReference] = {}

        for view, containers in self.containers_by_view.items():
            if len(containers) < 2:
                continue

            modifiable = containers.intersection(self.modifiable_containers)
            if not modifiable:
                continue

            # Score: (view_count, no_existing_penalty, alphabetical)
            result[view] = min(
                modifiable,
                key=lambda c: (
                    len(self.views_by_container.get(c, set())),
                    0 if any((c, other) in self._existing_requires_edges for other in containers) else 1,
                    str(c),
                ),
            )

        return result

    @cached_property
    def _views_with_root_conflicts(self) -> set[ViewReference]:
        """Views where all modifiable containers are forced roots for other views.

        A view has root conflicts if:
        1. It has no immutable containers (no shared CDM anchor)
        2. All its modifiable containers are already forced roots for other views

        Such views would require edges between forced roots, causing conflicts.
        """
        forced_roots = set(self._root_by_view.values())
        unsolvable: set[ViewReference] = set()

        for view, containers in self.containers_by_view.items():
            modifiable = containers & self.modifiable_containers
            immutable = containers - self.modifiable_containers

            # Need at least 2 modifiable containers to have a conflict
            if len(modifiable) < 2:
                continue

            # No immutable anchor AND all modifiables are roots elsewhere
            if not immutable and modifiable <= forced_roots:
                unsolvable.add(view)

        return unsolvable

    @cached_property
    def oriented_mst_edges(self) -> set[tuple[ContainerReference, ContainerReference]]:
        """Orient per-view MST edges by voting across views.

        Each view votes for edge orientations based on BFS from its root container.
        Views with only 1 modifiable container use 'inf' vote weight to force
        that container as root.

        Tie-breaker: preferred_direction from weight function.

        Returns set of directed (src, dst) tuples.
        """
        edge_votes: dict[tuple[ContainerReference, ContainerReference], float] = defaultdict(float)
        all_edges: set[tuple[ContainerReference, ContainerReference]] = set()

        # Sort for deterministic iteration (dict order can vary with hash randomization)
        for view in sorted(self._mst_by_view.keys(), key=str):
            mst = self._mst_by_view[view]
            root = self._root_by_view[view]  # Always exists for views in _mst_by_view
            containers = self.containers_by_view.get(view)
            modifiable_count = len(containers & self.modifiable_containers)
            # Views with only 1 modifiable container have no choice - that container MUST be root
            vote_weight = float("inf") if modifiable_count == 1 else 1.0

            # BFS from root orients edges away from root (parent → child)
            for parent, child in nx.bfs_edges(mst, root):
                if parent in self.modifiable_containers:
                    edge_votes[(parent, child)] += vote_weight

            # Normalize edges to canonical form so votes for same undirected edge are counted together
            for c1, c2 in mst.edges():
                all_edges.add((c1, c2) if str(c1) < str(c2) else (c2, c1))

        # Pick direction: most votes wins, preferred_direction breaks ties
        oriented: set[tuple[ContainerReference, ContainerReference]] = set()

        # Sort for deterministic iteration (hash randomization affects set order)
        for c1, c2 in sorted(all_edges, key=lambda e: (str(e[0]), str(e[1]))):
            c1_votes = edge_votes.get((c1, c2), 0)
            c2_votes = edge_votes.get((c2, c1), 0)

            if c1_votes > c2_votes:
                oriented.add((c1, c2))
            elif c2_votes > c1_votes:
                oriented.add((c2, c1))
            else:
                # Tie-breaker: use preferred_direction from weight function
                oriented.add(self._requires_candidate_graph[c1][c2].get("preferred_direction", (c1, c2)))

        return oriented

    @cached_property
    def _transitively_reduced_edges(self) -> set[tuple[ContainerReference, ContainerReference]]:
        """Reduce MST edges to minimal necessary set (remove edges with alternative paths via immutable)."""
        if not self.oriented_mst_edges:
            return set()

        # Optimal graph = MST + immutable + user-intentional (these provide existing paths)
        optimal = nx.DiGraph()
        optimal.add_edges_from(self.immutable_requires_constraint_graph.edges())
        optimal.add_edges_from(self._user_intentional_constraints)
        optimal.add_edges_from(self.oriented_mst_edges)

        reduced = nx.transitive_reduction(optimal)

        # Return MST edges that survive reduction
        return {e for e in reduced.edges() if e in self.oriented_mst_edges}

    def get_requires_changes_for_view(self, view: ViewReference) -> RequiresChangesForView:
        """Get requires constraint changes needed to optimize a view.

        Returns a RequiresChangesForView with:
        - to_add: New constraints needed where source is mapped in this view
        - to_remove: Existing constraints that are redundant or wrongly oriented
        - status: The optimization status for this view
        """
        modifiable_containers_in_view = self.containers_by_view.get(view).intersection(self.modifiable_containers)
        if not modifiable_containers_in_view:
            return RequiresChangesForView(set(), set(), RequiresChangeStatus.NO_MODIFIABLE_CONTAINERS)

        # Early exit for inherently unsolvable views (no CDM anchor + all modifiables are roots)
        if view in self._views_with_root_conflicts:
            return RequiresChangesForView(
                set[tuple[ContainerReference, ContainerReference]](), set(), RequiresChangeStatus.UNSOLVABLE
            )

        # Filter edges to those where source is in this view's modifiable containers
        existing_from_view = {
            edge for edge in self._existing_requires_edges if edge[0] in modifiable_containers_in_view
        }
        optimal_for_view = {
            edge for edge in self._transitively_reduced_edges if edge[0] in modifiable_containers_in_view
        }

        to_add = optimal_for_view - existing_from_view

        # To remove: existing edges with wrong direction or not in MST (and not needed externally)
        # But NEVER remove user-intentional constraints (manually defined, no __auto postfix)
        to_remove: set[tuple[ContainerReference, ContainerReference]] = set()
        for src, dst in existing_from_view:
            # Skip user-intentional constraints - they were set by the user on purpose
            if (src, dst) in self._user_intentional_constraints:
                continue
            if (dst, src) in self.oriented_mst_edges:
                to_remove.add((src, dst))  # Always remove if opposite direction from optimal solution
            elif (src, dst) not in self.oriented_mst_edges and not (
                self.find_views_mapping_to_containers([src, dst]) - set(self.merged.views)
            ):
                to_remove.add((src, dst))  # Remove if not in optimal solution and not needed by external views

        # Check solvability in optimized state
        if not self.forms_directed_path(self.containers_by_view.get(view), self.optimized_requires_constraint_graph):
            return RequiresChangesForView(set(), set(), RequiresChangeStatus.UNSOLVABLE)

        if not to_add and not to_remove:
            return RequiresChangesForView(set(), set(), RequiresChangeStatus.OPTIMAL)

        return RequiresChangesForView(to_add, to_remove, RequiresChangeStatus.CHANGES_AVAILABLE)

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
    #   - Tier 1 (USER→USER):     Both containers modifiable - always preferred
    #   - Tier 2 (USER→EXTERNAL): Target is CDF/CDM - only when needed
    #   - Tier ∞ (FORBIDDEN):     Invalid edge, forms cycle or source is not modifiable
    #
    # Sub-weights refine ordering WITHIN a tier (shared views, direction, etc).
    #   - These have been empirically tuned through trial and error.
    # ========================================================================

    # Tier base weights (gap of 1000 ensures tier always wins)
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
        # Opposite direction of fixed constraints is forbidden (would conflict with existing path)
        if src in self._fixed_descendants[dst]:
            return self._TIER_FORBIDDEN

        if src not in self.modifiable_containers:
            return self._TIER_FORBIDDEN

        src_views = self.views_by_container.get(src, set())
        dst_views = self.views_by_container.get(dst, set())

        # Sub-weight adjustments
        shared_bonus = min(len(src_views & dst_views) * self._BONUS_SHARED_VIEWS_PER, self._BONUS_SHARED_VIEWS_MAX)
        coverage_bonus = min(len(self._fixed_descendants[dst]) * self._BONUS_COVERAGE_PER, self._BONUS_COVERAGE_MAX)
        view_penalty = self._PENALTY_VIEW_COUNT if len(src_views) > len(dst_views) else 0

        # Deterministic tie-breaker (very small, only matters when all else is equal)
        edge_str = f"{src.space}:{src.external_id}->{dst.space}:{dst.external_id}"
        tie_breaker = sum(ord(c) for c in edge_str) / self._TIE_BREAKER_DIVISOR

        if dst in self.modifiable_containers:
            return self._TIER_USER_TO_USER - shared_bonus - coverage_bonus + view_penalty + tie_breaker

        return self._TIER_USER_TO_EXTERNAL - shared_bonus - coverage_bonus + tie_breaker
