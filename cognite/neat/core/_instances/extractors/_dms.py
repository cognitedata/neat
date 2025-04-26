import typing
from collections.abc import Iterable, Set

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import DataModelIdentifier
from cognite.client.data_classes.data_modeling.instances import Instance
from cognite.client.utils.useful_types import SequenceNotStr
from rdflib import Namespace

from cognite.neat.core._client import NeatClient
from cognite.neat.core._issues.errors import ResourceRetrievalError
from cognite.neat.core._shared import Triple

from ._base import BaseExtractor
from ._dict import DEFAULT_EMPTY_VALUES
from ._instances import InstancesExtractor
from ._views import _ViewInstanceIterator


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
    ) -> None:
        self.total_instances_pair_by_view = total_instances_pair_by_view
        self.limit = limit
        self.overwrite_namespace = overwrite_namespace
        self.unpack_json = unpack_json
        self.empty_values = empty_values
        self.str_to_ideal_type = str_to_ideal_type
        self.node_type = node_type
        self.edge_type = edge_type

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
        for view_id, (total, instances) in self.total_instances_pair_by_view.items():
            if total == 0:
                continue
            instance_extractor = InstancesExtractor(
                instances,
                name=f"{view_id.space}:{view_id.external_id}(version={view_id.version})",
                total=total,
                limit=self.limit,
                overwrite_namespace=self.overwrite_namespace,
                unpack_json=self.unpack_json,
                empty_values=self.empty_values,
                str_to_ideal_type=self.str_to_ideal_type,
                node_type=self.node_type,
                edge_type=self.edge_type,
            )

            yield from instance_extractor.extract()
