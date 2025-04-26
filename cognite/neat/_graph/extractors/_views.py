import typing
from collections.abc import Iterable, Set

from cognite.client.data_classes.data_modeling import ViewId, ViewIdentifier
from cognite.client.data_classes.data_modeling.instances import Instance
from cognite.client.utils.useful_types import SequenceNotStr
from rdflib import Namespace

from cognite.neat._client import NeatClient
from cognite.neat._issues.errors import ResourceRetrievalError
from cognite.neat._shared import Triple

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
        latest_view = retrieved_list.latest_version()
        instance_iterator = _ViewInstanceIterator(client, latest_view, instance_space)
        total = instance_iterator.total
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
