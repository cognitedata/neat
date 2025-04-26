import typing
from collections.abc import Iterable, Iterator, Set
from functools import cached_property

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import ViewId, ViewIdentifier
from cognite.client.data_classes.data_modeling.instances import Instance
from cognite.client.utils.useful_types import SequenceNotStr
from rdflib import Namespace

from cognite.neat.core._client import NeatClient
from cognite.neat.core._constants import is_readonly_property
from cognite.neat.core._issues.errors import ResourceRetrievalError
from cognite.neat.core._shared import Triple

from ._base import BaseExtractor
from ._dict import DEFAULT_EMPTY_VALUES
from ._instances import InstancesExtractor


class ViewExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusion instances with properties in a view into Neat.
    Args:
        view_id: The view id to extract from.
        instances: The instances to extract from.
        total: The total number of items to extract. If None, it will be calculated from the instances.
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
        view_id: ViewId,
        instances: Iterable[Instance],
        total: int | None = None,
        limit: int | None = None,
        overwrite_namespace: Namespace | None = None,
        unpack_json: bool = False,
        empty_values: Set[str] = DEFAULT_EMPTY_VALUES,
        str_to_ideal_type: bool = False,
        node_type: tuple[typing.Literal["view", "type"], ...] = ("view",),
        edge_type: tuple[typing.Literal["view", "type"], ...] = ("view", "type"),
    ) -> None:
        self.view_id = view_id
        self.instances = instances
        self.total = total
        self.limit = limit
        self.overwrite_namespace = overwrite_namespace
        self.unpack_json = unpack_json
        self.empty_values = empty_values
        self.str_to_ideal_type = str_to_ideal_type
        self.node_type = node_type
        self.edge_type = edge_type

    @classmethod
    def from_view(
        cls,
        client: NeatClient,
        view_id: ViewIdentifier,
        limit: int | None = None,
        overwrite_namespace: Namespace | None = None,
        instance_space: str | SequenceNotStr[str] | None = None,
        unpack_json: bool = False,
        str_to_ideal_type: bool = False,
    ) -> "ViewExtractor":
        """Create an extractor for a single view
        Args:
            client: The Cognite client to use.
            view_id: The identifier of the view to extract from.
            limit: The maximum number of instances to extract.
            overwrite_namespace: If provided, this will overwrite the space of the extracted items.
            instance_space: The space to extract instances from.
            unpack_json: If True, JSON objects will be unpacked into RDF literals.
            str_to_ideal_type: If True, when unpacking JSON objects, if the value is a string, the extractor will try to
                convert it to the ideal type.
        """
        retrieved_list = client.data_modeling.views.retrieve(view_id)
        if not retrieved_list:
            raise ResourceRetrievalError(ViewId.load(view_id), "view", "View is missing in CDF")
        latest_view = max(retrieved_list, key=lambda v: v.last_updated_time)
        instance_iterator = _ViewInstanceIterator(client, latest_view, instance_space)
        total = instance_iterator.count
        return cls(
            latest_view.as_id(),
            instance_iterator,
            total=total,
            limit=limit,
            overwrite_namespace=overwrite_namespace,
            unpack_json=unpack_json,
            str_to_ideal_type=str_to_ideal_type,
        )

    def extract(self) -> Iterable[Triple]:
        if self.total == 0:
            return
        view_id = self.view_id
        instance_iterator = InstancesExtractor(
            self.instances,
            name=f"{view_id.space}:{view_id.external_id}(version={view_id.version})",
            total=self.total,
            limit=self.limit,
            overwrite_namespace=self.overwrite_namespace,
            unpack_json=self.unpack_json,
            empty_values=self.empty_values,
            str_to_ideal_type=self.str_to_ideal_type,
            node_type=self.node_type,
            edge_type=self.edge_type,
        )
        yield from instance_iterator.extract()


class _ViewInstanceIterator(Iterable[Instance]):
    def __init__(self, client: NeatClient, view: dm.View, instance_space: str | SequenceNotStr[str] | None = None):
        self.client = client
        self.view = view
        self.instance_space = instance_space

    @cached_property
    def count(self) -> int:
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
        # All nodes and edges with properties
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

    @staticmethod
    def _remove_read_only_properties(
        nodes: Iterable[Instance], read_only_properties: Set[str], view_id: dm.ViewId
    ) -> Iterable[Instance]:
        for node in nodes:
            if properties := node.properties.get(view_id):
                for read_only in read_only_properties:
                    properties.pop(read_only, None)
            yield node
