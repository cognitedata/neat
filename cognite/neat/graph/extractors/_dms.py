from collections.abc import Iterable
from typing import cast

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.instances import Instance, PropertyValue
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.graph.models import Triple

from ._base import BaseExtractor


class DMSExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusion DMS instances into Neat."""

    def __init__(self, items: Iterable[Instance], total: int | None = None, limit: int | None = None) -> None:
        self.items = items
        self.total = total
        self.limit = limit
        self._namespace_by_space: dict[str, Namespace] = {}

    def extract(self) -> Iterable[Triple]:
        for count, item in enumerate(self.items, 1):
            if self.limit and count > self.limit:
                break
            yield from self._extract_instance(item)

    def _extract_instance(self, instance: Instance) -> Iterable[Triple]:
        id_ = self._as_uri_ref(instance)
        if isinstance(instance, dm.Edge) or (isinstance(instance, dm.Node) and instance.type):
            type_ = self._as_uri_ref(cast(dm.DirectRelationReference, instance.type))
        elif isinstance(instance, dm.Node):
            type_ = self._as_uri_ref(dm.DirectRelationReference(instance.space, "Node"))
        else:
            raise NotImplementedError(f"Unknown instance type {type(instance)}")

        yield id_, RDF.type, type_

        for view_id, properties in instance.properties.items():
            namespace = self._get_namespace(view_id.space)
            for key, value in properties.items():
                for object_ in self._get_objects(value):
                    yield id_, namespace[key], object_

        if isinstance(instance, dm.Edge):
            yield id_, self._get_namespace("Edge").startNode, self._as_uri_ref(instance.start_node)
            yield id_, self._get_namespace("Edge").endNode, self._as_uri_ref(instance.end_node)

    def _get_objects(self, value: PropertyValue) -> Iterable[Literal | URIRef]:
        if isinstance(value, str | float | bool | int):
            yield Literal(value)
        elif isinstance(value, dict) and "space" in value and "externalId" in value:
            yield self._as_uri_ref(dm.DirectRelationReference.load(value))
        elif isinstance(value, dict):
            yield Literal(str(value))
        elif isinstance(value, list):
            for item in value:
                yield from self._get_objects(item)

    def _as_uri_ref(self, instance: Instance | dm.DirectRelationReference) -> URIRef:
        return self._get_namespace(instance.space)[instance.external_id]

    def _get_namespace(self, space: str) -> Namespace:
        if space not in self._namespace_by_space:
            self._namespace_by_space[space] = Namespace(space)
        return self._namespace_by_space[space]
