import typing
import urllib.parse
from collections.abc import Callable, Iterable, Set

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.instances import Edge, Instance, Node
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.core._config import GLOBAL_CONFIG
from cognite.neat.core._constants import DEFAULT_SPACE_URI
from cognite.neat.core._shared import Triple
from cognite.neat.core._utils.collection_ import iterate_progress_bar

from ._base import BaseExtractor
from ._dict import DEFAULT_EMPTY_VALUES, DMSPropertyExtractor


class InstancesExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusion instances into Neat.

    This is the basis used for the DataModeling and View extractors.

    Args:
        instances: The instances to extract.
        name: The name of the instances. This is used for the progress bar. Typically, the view the instances are from.
        total: The total number of items to extract. This is required for the progress bar.
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
        instances: Iterable[Instance],
        name: str | None = None,
        total: int | None = None,
        limit: int | None = None,
        overwrite_namespace: Namespace | None = None,
        unpack_json: bool = False,
        empty_values: Set[str] = DEFAULT_EMPTY_VALUES,
        str_to_ideal_type: bool = False,
        node_type: tuple[typing.Literal["view", "type"], ...] = ("view",),
        edge_type: tuple[typing.Literal["view", "type"], ...] = ("view", "type"),
    ) -> None:
        self.instances = instances
        self.name = name
        self.total = total
        self.limit = limit
        self.overwrite_namespace = overwrite_namespace
        self.unpack_json = unpack_json
        self.empty_values = empty_values
        self.str_to_ideal_type = str_to_ideal_type
        self.node_type = node_type
        self.edge_type = edge_type

    def extract(self) -> Iterable[Triple]:
        if self.total == 0:
            return
        use_progress_bar = (
            self.total
            and GLOBAL_CONFIG.use_iterate_bar_threshold
            and self.total > GLOBAL_CONFIG.use_iterate_bar_threshold
        )

        instances = self.instances
        if use_progress_bar and self.total is not None:
            name = self.name or "instances"
            instances = iterate_progress_bar(
                instances,
                self.total,
                f"Extracting instances from {name}",
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
