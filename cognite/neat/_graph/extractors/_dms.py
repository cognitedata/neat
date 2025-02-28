import urllib.parse
from collections.abc import Iterable, Iterator, Set
from functools import cached_property
from typing import cast

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import DataModelIdentifier
from cognite.client.data_classes.data_modeling.instances import Instance, InstanceSort
from cognite.client.utils.useful_types import SequenceNotStr
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat._config import GLOBAL_CONFIG
from cognite.neat._constants import DEFAULT_SPACE_URI, is_readonly_property
from cognite.neat._issues.errors import ResourceRetrievalError
from cognite.neat._shared import Triple
from cognite.neat._utils.collection_ import iterate_progress_bar

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
    """

    def __init__(
        self,
        total_instances_pair_by_view: dict[dm.ViewId, tuple[int | None, Iterable[Instance]]],
        limit: int | None = None,
        overwrite_namespace: Namespace | None = None,
        unpack_json: bool = False,
        empty_values: Set[str] = DEFAULT_EMPTY_VALUES,
        str_to_ideal_type: bool = False,
    ) -> None:
        self.total_instances_pair_by_view = total_instances_pair_by_view
        self.limit = limit
        self.overwrite_namespace = overwrite_namespace
        self.unpack_json = unpack_json
        self.empty_values = empty_values
        self.str_to_ideal_type = str_to_ideal_type

    @classmethod
    def from_data_model(
        cls,
        client: CogniteClient,
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
        client: CogniteClient,
        views: Iterable[dm.View],
        limit: int | None = None,
        overwrite_namespace: Namespace | None = None,
        instance_space: str | SequenceNotStr[str] | None = None,
        unpack_json: bool = False,
        str_to_ideal_type: bool = False,
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
        """
        total_instances_pair_by_view: dict[dm.ViewId, tuple[int | None, Iterable[Instance]]] = {}
        for view in views:
            instance_iterator = _ViewInstanceIterator(client, view, instance_space)
            total_instances_pair_by_view[view.as_id()] = (instance_iterator.count, instance_iterator)

        return cls(
            total_instances_pair_by_view=total_instances_pair_by_view,
            limit=limit,
            overwrite_namespace=overwrite_namespace,
            unpack_json=unpack_json,
            str_to_ideal_type=str_to_ideal_type,
        )

    def extract(self) -> Iterable[Triple]:
        total_instances = sum(total for total, _ in self.total_instances_pair_by_view.values() if total is not None)
        use_progress_bar = (
            GLOBAL_CONFIG.use_iterate_bar_threshold and total_instances > GLOBAL_CONFIG.use_iterate_bar_threshold
        )

        for view_id, (total, instances) in self.total_instances_pair_by_view.items():
            if total == 0:
                continue
            if use_progress_bar and total is not None:
                instances = iterate_progress_bar(
                    instances,
                    total,
                    f"Extracting instances from {view_id.space}:{view_id.external_id}(version={view_id.version})",
                )

            for count, item in enumerate(instances, 1):
                if self.limit and count > self.limit:
                    break
                yield from self._extract_instance(item)

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
                yield id_, RDF.type, self._as_uri_ref(instance.type)
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
            if instance.type:
                type_ = self._as_uri_ref(cast(dm.DirectRelationReference, instance.type))
            elif len(instance.properties) == 1:
                view_id = next(iter(instance.properties.keys()))
                type_ = self._get_namespace(view_id.space)[urllib.parse.quote(view_id.external_id)]
            else:
                type_ = self._get_namespace(instance.space).Node

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

    def _as_uri_ref(self, instance: Instance | dm.DirectRelationReference) -> URIRef:
        return self._get_namespace(instance.space)[urllib.parse.quote(instance.external_id)]

    def _get_namespace(self, space: str) -> Namespace:
        if self.overwrite_namespace:
            return self.overwrite_namespace
        return Namespace(DEFAULT_SPACE_URI.format(space=urllib.parse.quote(space)))


class _ViewInstanceIterator(Iterable[Instance]):
    def __init__(self, client: CogniteClient, view: dm.View, instance_space: str | SequenceNotStr[str] | None = None):
        self.client = client
        self.view = view
        self.instance_space = instance_space

    @cached_property
    def count(self) -> int:
        node_count = edge_count = 0
        if self.view.used_for in ("node", "all"):
            node_count = int(
                self.client.data_modeling.instances.aggregate(
                    view=self.view.as_id(),
                    aggregates=dm.aggregations.Count("externalId"),
                    instance_type="node",
                    space=self.instance_space,
                ).value
            )
        if self.view.used_for in ("edge", "all"):
            edge_count = int(
                self.client.data_modeling.instances.aggregate(
                    view=self.view.as_id(),
                    aggregates=dm.aggregations.Count("externalId"),
                    instance_type="edge",
                    space=self.instance_space,
                ).value
            )
        return node_count + edge_count

    def __iter__(self) -> Iterator[Instance]:
        view_id = self.view.as_id()
        read_only_properties = {
            prop_id
            for prop_id, prop in self.view.properties.items()
            if isinstance(prop, dm.MappedProperty)
            and is_readonly_property(prop.container, prop.container_property_identifier)
        }
        # All nodes and edges with properties
        if self.view.used_for in ("node", "all"):
            # Without a sort, the sort is implicitly by the internal id, as cursoring needs a stable sort.
            # By making the sort be on external_id, Postgres should pick the index
            # that's on (project_id, space, external_id)
            # WHERE deleted_at IS NULL. In other words, avoiding soft deleted instances.
            node_iterable: Iterable[Instance] = self.client.data_modeling.instances(
                chunk_size=None,
                instance_type="node",
                sources=[view_id],
                space=self.instance_space,
                sort=InstanceSort(["node", "externalId"]),
            )
            if read_only_properties:
                node_iterable = self._remove_read_only_properties(node_iterable, read_only_properties, view_id)
            yield from node_iterable

        if self.view.used_for in ("edge", "all"):
            yield from self.client.data_modeling.instances(
                chunk_size=None,
                instance_type="edge",
                sources=[view_id],
                space=self.instance_space,
                sort=InstanceSort(["edge", "externalId"]),
            )

        for prop in self.view.properties.values():
            if isinstance(prop, dm.EdgeConnection):
                if prop.edge_source:
                    # All edges with properties are extracted from the edge source
                    continue
                yield from self.client.data_modeling.instances(
                    chunk_size=None,
                    instance_type="edge",
                    filter=dm.filters.Equals(
                        ["edge", "type"], {"space": prop.type.space, "externalId": prop.type.external_id}
                    ),
                    space=self.instance_space,
                    sort=InstanceSort(["edge", "externalId"]),
                )

    @staticmethod
    def _remove_read_only_properties(
        nodes: Iterable[Instance], read_only_properties: Set[str], view_id: dm.ViewId
    ) -> Iterable[Instance]:
        for node in nodes:
            if properties := node.properties.get(view_id):
                for read_only in read_only_properties:
                    properties.pop(read_only, None)
            yield node
