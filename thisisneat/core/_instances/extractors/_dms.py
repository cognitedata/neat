import typing
import urllib.parse
from collections.abc import Callable, Iterable, Iterator, Set
from functools import cached_property

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import DataModelIdentifier
from cognite.client.data_classes.data_modeling.instances import Edge, Instance, Node
from cognite.client.utils.useful_types import SequenceNotStr
from rdflib import RDF, Literal, Namespace, URIRef

from thisisneat.core._client import NeatClient
from thisisneat.core._config import GLOBAL_CONFIG
from thisisneat.core._constants import DEFAULT_SPACE_URI, is_readonly_property
from thisisneat.core._issues.errors import ResourceRetrievalError
from thisisneat.core._shared import Triple
from thisisneat.core._utils.collection_ import iterate_progress_bar

from ._base import BaseExtractor
from ._dict import DEFAULT_EMPTY_VALUES, DMSPropertyExtractor


class DMSExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusion DMS instances into Neat.

    Args:
        total_instances_pair_by_view: A dictionary where the key is the view id and the value is a tuple with the total
            number of instances and an iterable of instances.
        limit: The maximum number of items to extract.
        overwrite_namespace: If provided, this will overwrite the space of the extracted items.
        unpack_json: If True, JSON objects will be unpacked into RDF literals.
        empty_values: If unpack_json is True, when unpacking JSON objects, if a key has a value in this set, it will be
            considered as an empty value and skipped.
        str_to_ideal_type: If unpack_json is True, when unpacking JSON objects, if the value is a string, the extractor
            will try to convert it to the ideal type.
        node_type: The prioritized order of the node type to use. The options are "view" and "type". "view"
            means the externalId of the view used as type, while type is the node.type.
        edge_type: The prioritized order of the edge type to use. The options are "view" and "type". "view"
            means the externalId of the view used as type, while type is the edge.type.
    """

    def __init__(
        self,
        total_instances_pair_by_view: dict[dm.ViewId, tuple[int | None, Iterable[Instance]]],
        limit: int | None = None,
        overwrite_namespace: Namespace | None = None,
        unpack_json: bool = False,
        empty_values: Set[str] = DEFAULT_EMPTY_VALUES,
        str_to_ideal_type: bool = False,
        node_type: tuple[typing.Literal["view", "type"], ...] = ("view",),
        edge_type: tuple[typing.Literal["view", "type"], ...] = ("view", "type"),
        cursors: dict[str, str] | None = None,
    ) -> None:
        self.total_instances_pair_by_view = total_instances_pair_by_view
        self.limit = limit
        self.overwrite_namespace = overwrite_namespace
        self.unpack_json = unpack_json
        self.empty_values = empty_values
        self.str_to_ideal_type = str_to_ideal_type
        self.node_type = node_type
        self.edge_type = edge_type
        self.cursors = cursors
        self._result_cursors: dict[str, str] = {}

    @classmethod
    def from_data_model(
        cls,
        client: NeatClient,
        data_model: DataModelIdentifier,
        limit: int | None = None,
        overwrite_namespace: Namespace | None = None,
        instance_space: str | SequenceNotStr[str] | None = None,
        unpack_json: bool = False,
        str_to_ideal_type: bool = False,
    ) -> "DMSExtractor":
        """Create an extractor from a data model.

        Args:
            client: The Cognite client to use.
            data_model: The data model to extract.
            limit: The maximum number of instances to extract.
            overwrite_namespace: If provided, this will overwrite the space of the extracted items.
            instance_space: The space to extract instances from.
            unpack_json: If True, JSON objects will be unpacked into RDF literals.
        """
        retrieved = client.data_modeling.data_models.retrieve(data_model, inline_views=True)
        if not retrieved:
            raise ResourceRetrievalError(dm.DataModelId.load(data_model), "data model", "Data Model is missing in CDF")
        return cls.from_views(
            client,
            retrieved.latest_version().views,
            limit,
            overwrite_namespace,
            instance_space,
            unpack_json,
            str_to_ideal_type,
        )

    @classmethod
    def from_views(
        cls,
        client: NeatClient,
        views: Iterable[dm.View],
        limit: int | None = None,
        overwrite_namespace: Namespace | None = None,
        instance_space: str | SequenceNotStr[str] | None = None,
        unpack_json: bool = False,
        str_to_ideal_type: bool = False,
        cursors: dict[str, str] | None = None,
    ) -> "DMSExtractor":
        """Create an extractor from a set of views.

        Args:
            client: The Cognite client to use.
            views: The views to extract.
            limit: The maximum number of instances to extract.
            overwrite_namespace: If provided, this will overwrite the space of the extracted items.
            instance_space: The space to extract instances from.
            unpack_json: If True, JSON objects will be unpacked into RDF literals.
            str_to_ideal_type: If True, when unpacking JSON objects, if the value is a string, the extractor will try to
                convert it to the ideal type.
            cursors: Optional cursors for incremental sync.
        """
        total_instances_pair_by_view: dict[dm.ViewId, tuple[int | None, Iterable[Instance]]] = {}
        for view in views:
            instance_iterator = _ViewInstanceIterator(client, view, instance_space, cursors)
            total_instances_pair_by_view[view.as_id()] = (instance_iterator.count, instance_iterator)

        return cls(
            total_instances_pair_by_view=total_instances_pair_by_view,
            limit=limit,
            overwrite_namespace=overwrite_namespace,
            unpack_json=unpack_json,
            str_to_ideal_type=str_to_ideal_type,
            cursors=cursors,
        )

    def extract(self) -> Iterable[Triple]:
        total_instances = sum(total for total, _ in self.total_instances_pair_by_view.values() if total is not None)
        use_progress_bar = (
            GLOBAL_CONFIG.use_iterate_bar_threshold and total_instances > GLOBAL_CONFIG.use_iterate_bar_threshold
        )
        
        # Check if this is an incremental sync (any view has None count)
        is_incremental_sync = any(total is None for total, _ in self.total_instances_pair_by_view.values())

        for view_id, (total, instances) in self.total_instances_pair_by_view.items():
            if total == 0:
                continue
            
            # Keep reference to original iterator before wrapping
            original_iterator = instances
            
            if use_progress_bar and total is not None:
                instances = iterate_progress_bar(
                    instances,
                    total,
                    f"Extracting instances from {view_id.space}:{view_id.external_id}(version={view_id.version})",
                )
            elif is_incremental_sync and total is None:
                # For incremental sync without progress bar, print a simple message
                print(f"Syncing changes from {view_id.space}:{view_id.external_id}(version={view_id.version})...", end="")

            instance_count = 0
            for count, item in enumerate(instances, 1):
                if self.limit and count > self.limit:
                    break
                instance_count += 1
                yield from self._extract_instance(item)
            
            # Print count for incremental sync
            if is_incremental_sync and total is None:
                if instance_count > 0:
                    print(f" {instance_count} change(s)")
                else:
                    print(" no changes")
            
            # Collect cursors after iterating through this view
            # Use original iterator reference to get cursors
            if isinstance(original_iterator, _ViewInstanceIterator):
                cursors = original_iterator.get_cursors()
                self._result_cursors.update(cursors)
    
    def get_cursors(self) -> dict[str, str]:
        """Returns the cursors from the last extraction for incremental sync."""
        return self._result_cursors

    def _extract_instance(self, instance: Instance) -> Iterable[Triple]:
        if isinstance(instance, dm.Edge):
            if not instance.properties:
                yield (
                    self._as_uri_ref(instance.start_node),
                    self._as_uri_ref(instance.type),
                    self._as_uri_ref(instance.end_node),
                )
                return
            else:
                # If the edge has properties, we create a node for the edge and connect it to the start and end nodes.
                id_ = self._as_uri_ref(instance)
                type_ = self._create_type(
                    instance, fallback=self._get_namespace(instance.space).Edge, type_priority=self.edge_type
                )
                yield id_, RDF.type, type_
                yield (
                    id_,
                    self._as_uri_ref(dm.DirectRelationReference(instance.space, "startNode")),
                    self._as_uri_ref(instance.start_node),
                )
                yield (
                    id_,
                    self._as_uri_ref(dm.DirectRelationReference(instance.space, "endNode")),
                    self._as_uri_ref(instance.end_node),
                )

        elif isinstance(instance, dm.Node):
            id_ = self._as_uri_ref(instance)
            type_ = self._create_type(
                instance, fallback=self._get_namespace(instance.space).Node, type_priority=self.node_type
            )
            yield id_, RDF.type, type_
        else:
            raise NotImplementedError(f"Unknown instance type {type(instance)}")

        if self.overwrite_namespace:
            # If the namespace is overwritten, keep the original space as a property to avoid losing information.
            yield id_, self._get_namespace(instance.space)["space"], Literal(instance.space)

        for view_id, properties in instance.properties.items():
            namespace = self._get_namespace(view_id.space)
            yield from DMSPropertyExtractor(
                id_,
                properties,
                namespace,
                self._as_uri_ref,
                self.empty_values,
                self.str_to_ideal_type,
                self.unpack_json,
            ).extract()

    def _create_type(
        self, instance: Node | Edge, fallback: URIRef, type_priority: tuple[typing.Literal["view", "type"], ...]
    ) -> URIRef:
        method_by_name: dict[str, Callable[[Node | Edge], URIRef | None]] = {
            "view": self._view_to_rdf_type,
            "type": self._instance_type_to_rdf,
        }
        for method_name in type_priority:
            type_ = method_by_name[method_name](instance)
            if type_:
                return type_
        else:
            return fallback

    def _instance_type_to_rdf(self, instance: Node | Edge) -> URIRef | None:
        if instance.type:
            return self._as_uri_ref(instance.type)
        return None

    def _view_to_rdf_type(self, instance: Node | Edge) -> URIRef | None:
        view_id = next(iter((instance.properties or {}).keys()), None)
        if view_id:
            return self._get_namespace(view_id.space)[urllib.parse.quote(view_id.external_id)]
        return None

    def _as_uri_ref(self, instance: Instance | dm.DirectRelationReference) -> URIRef:
        return self._get_namespace(instance.space)[urllib.parse.quote(instance.external_id)]

    def _get_namespace(self, space: str) -> Namespace:
        if self.overwrite_namespace:
            return self.overwrite_namespace
        return Namespace(DEFAULT_SPACE_URI.format(space=urllib.parse.quote(space)))


class _ViewInstanceIterator(Iterable[Instance]):
    def __init__(
        self, 
        client: NeatClient, 
        view: dm.View, 
        instance_space: str | SequenceNotStr[str] | None = None,
        cursors: dict[str, str] | None = None,
    ):
        self.client = client
        self.view = view
        self.instance_space = instance_space
        self.cursors = cursors
        self._result_cursors: dict[str, str] = {}

    @cached_property
    def count(self) -> int | None:
        # For incremental sync, we don't know the count upfront, so return None to disable progress bar
        if self.cursors:
            return None
        
        node_count = edge_count = 0
        if self.view.used_for in ("node", "all"):
            node_result = self.client.data_modeling.instances.aggregate(
                view=self.view.as_id(),
                aggregates=dm.aggregations.Count("externalId"),
                instance_type="node",
                space=self.instance_space,
            ).value
            if node_result:
                node_count = int(node_result)
        if self.view.used_for in ("edge", "all"):
            edge_result = self.client.data_modeling.instances.aggregate(
                view=self.view.as_id(),
                aggregates=dm.aggregations.Count("externalId"),
                instance_type="edge",
                space=self.instance_space,
            ).value
            if edge_result:
                edge_count = int(edge_result)
        return node_count + edge_count

    def __iter__(self) -> Iterator[Instance]:
        view_id = self.view.as_id()
        read_only_properties = {
            prop_id
            for prop_id, prop in self.view.properties.items()
            if isinstance(prop, dm.MappedProperty)
            and is_readonly_property(prop.container, prop.container_property_identifier)
        }
        
        # If cursors provided, use sync endpoint for incremental updates
        if self.cursors:
            yield from self._sync_instances(view_id, read_only_properties)
        else:
            # No cursors - use list endpoint for full load
            yield from self._list_instances(view_id, read_only_properties)
    
    def _sync_instances(self, view_id: dm.ViewId, read_only_properties: Set[str]) -> Iterator[Instance]:
        """Use sync endpoint with cursors for incremental updates"""
        from cognite.client.data_classes.data_modeling.query import Query, Select, SourceSelector
        from cognite.client.data_classes.data_modeling.query import NodeResultSetExpression, EdgeResultSetExpression
        from cognite.client.data_classes.filters import HasData, Equals
        from cognite.client.exceptions import CogniteAPIError
        import time
        
        view_properties = list(self.view.properties.keys())
        view_key = f"{view_id.space}:{view_id.external_id}:{view_id.version}"
        
        # Extract cursors for this specific view from the global cursors dict
        view_cursors = {}
        if self.cursors:
            # Find cursors that belong to this view
            for key, value in self.cursors.items():
                if key.startswith(f"{view_key}:"):
                    # Extract the cursor type (nodes/edges) from the key
                    cursor_type = key.split(":")[-1]
                    view_cursors[cursor_type] = value
        
        # Build query based on view type
        if self.view.used_for == "edge":
            query = Query(
                with_={"edges": EdgeResultSetExpression(
                    filter=Equals(["edge", "type"], {"space": view_id.space, "externalId": view_id.external_id})
                )},
                select={"edges": Select([SourceSelector(source=view_id, properties=view_properties)])},
                cursors=view_cursors if view_cursors else None,
            )
            instance_key = "edges"
        else:
            query = Query(
                with_={"nodes": NodeResultSetExpression(filter=HasData(views=[view_id]))},
                select={"nodes": Select([SourceSelector(source=view_id, properties=view_properties)])},
                cursors=view_cursors if view_cursors else None,
            )
            instance_key = "nodes"
        
        query_start_time = int(time.time() * 1000)
        
        try:
            res = self.client.data_modeling.instances.sync(query=query)
        except CogniteAPIError as e:
            if e.code == 400 and ("Invalid cursor" in str(e) or "Cursor has expired" in str(e)):
                # Invalid cursor, reset to None and use list instead
                self.cursors = None
                yield from self._list_instances(view_id, read_only_properties)
                return
            else:
                raise
        
        # Yield instances from sync
        while True:
            if instance_key in res.data:
                for instance in res.data[instance_key]:
                    if read_only_properties and instance_key == "nodes":
                        yield from self._remove_read_only_properties([instance], read_only_properties, view_id)
                    else:
                        yield instance
            
            # Check if we should continue
            if not (instance_key in res.data and len(res.data[instance_key]) > 0):
                break
            
            # Short-circuit if recent updates found
            if self._has_recent_update(res, query_start_time, instance_key):
                break
            
            # Continue with next page
            query.cursors = res.cursors
            res = self.client.data_modeling.instances.sync(query=query)
        
        # Store cursors with view-specific keys
        if res.cursors:
            if hasattr(res.cursors, '__dict__'):
                raw_cursors = dict(res.cursors.__dict__)
            elif isinstance(res.cursors, dict):
                raw_cursors = res.cursors
            else:
                raw_cursors = {}
            
            # Namespace cursors by view
            for cursor_type, cursor_value in raw_cursors.items():
                namespaced_key = f"{view_key}:{cursor_type}"
                self._result_cursors[namespaced_key] = cursor_value
    
    def _list_instances(self, view_id: dm.ViewId, read_only_properties: Set[str]) -> Iterator[Instance]:
        """Use list endpoint for full load (original logic)"""
        from cognite.client.data_classes.data_modeling.query import Query, Select, SourceSelector
        from cognite.client.data_classes.data_modeling.query import NodeResultSetExpression, EdgeResultSetExpression
        from cognite.client.data_classes.filters import Not, MatchAll
        
        view_properties = list(self.view.properties.keys())
        view_key = f"{view_id.space}:{view_id.external_id}:{view_id.version}"
        
        # FIRST: Run sync with empty filter to get current cursor (timestamp)
        # This ensures we don't miss any updates that happen during the list operation
        if self.view.used_for == "edge":
            query = Query(
                with_={"edges": EdgeResultSetExpression(filter=Not(MatchAll()))},
                select={"edges": Select([SourceSelector(source=view_id, properties=view_properties)])},
            )
        else:
            query = Query(
                with_={"nodes": NodeResultSetExpression(filter=Not(MatchAll()))},
                select={"nodes": Select([SourceSelector(source=view_id, properties=view_properties)])},
            )
        
        res = self.client.data_modeling.instances.sync(query=query)
        # Convert cursors to dict if needed
        if hasattr(res.cursors, '__dict__'):
            raw_cursors = dict(res.cursors.__dict__)
        elif isinstance(res.cursors, dict):
            raw_cursors = res.cursors
        else:
            raw_cursors = {}
        
        # Namespace cursors by view
        for cursor_type, cursor_value in raw_cursors.items():
            namespaced_key = f"{view_key}:{cursor_type}"
            self._result_cursors[namespaced_key] = cursor_value
        
        # THEN: Run list to get all instances
        # Any updates during this list will be caught in next sync using the cursor we just got
        if self.view.used_for in ("node", "all"):
            node_iterable: Iterable[Instance] = self.client.instances.iterate(
                instance_type="node",
                source=view_id,
                space=self.instance_space,
            )
            if read_only_properties:
                node_iterable = self._remove_read_only_properties(node_iterable, read_only_properties, view_id)
            yield from node_iterable

        if self.view.used_for in ("edge", "all"):
            yield from self.client.instances.iterate(
                instance_type="edge",
                source=view_id,
                space=self.instance_space,
            )

        for prop in self.view.properties.values():
            if isinstance(prop, dm.EdgeConnection):
                if prop.edge_source:
                    # All edges with properties are extracted from the edge source
                    continue
                yield from self.client.instances.iterate(
                    instance_type="edge",
                    filter_=dm.filters.Equals(
                        ["edge", "type"], {"space": prop.type.space, "externalId": prop.type.external_id}
                    ),
                    space=self.instance_space,
                )
    
    def _has_recent_update(self, result, query_start_time: int, instance_key: str) -> bool:
        """Check if any instance has lastUpdatedTime >= query_start_time"""
        if instance_key in result.data:
            for instance in result.data[instance_key]:
                if instance.last_updated_time >= query_start_time:
                    return True
        return False
    
    def get_cursors(self) -> dict[str, str]:
        """Returns the cursors from the last iteration"""
        return self._result_cursors

    @staticmethod
    def _remove_read_only_properties(
        nodes: Iterable[Instance], read_only_properties: Set[str], view_id: dm.ViewId
    ) -> Iterable[Instance]:
        for node in nodes:
            if properties := node.properties.get(view_id):
                for read_only in read_only_properties:
                    properties.pop(read_only, None)
            yield node
