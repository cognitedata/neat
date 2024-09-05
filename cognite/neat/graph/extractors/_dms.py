from collections.abc import Iterable
from typing import cast

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.instances import Instance, PropertyValue
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.graph.models import Triple

from ._base import BaseExtractor


class DMSExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusion DMS instances into Neat.

    Args:
        items: The items to extract.
        total: The total number of items to extract. If provided, this will be used to estimate the progress.
        limit: The maximum number of items to extract.
        overwrite_namespace: If provided, this will overwrite the space of the extracted items.
    """

    def __init__(
        self,
        items: Iterable[Instance],
        total: int | None = None,
        limit: int | None = None,
        overwrite_namespace: Namespace | None = None,
    ) -> None:
        self.items = items
        self.total = total
        self.limit = limit
        self.overwrite_namespace = overwrite_namespace
        self._namespace_by_space: dict[str, Namespace] = {}

    def extract(self) -> Iterable[Triple]:
        for count, item in enumerate(self.items, 1):
            if self.limit and count > self.limit:
                break
            yield from self._extract_instance(item)

    def _extract_instance(self, instance: Instance) -> Iterable[Triple]:
        if isinstance(instance, dm.Edge):
            yield (
                self._as_uri_ref(instance.start_node),
                self._as_uri_ref(instance.type),
                self._as_uri_ref(instance.end_node),
            )
        elif isinstance(instance, dm.Node):
            id_ = self._as_uri_ref(instance)
            if instance.type:
                type_ = self._as_uri_ref(cast(dm.DirectRelationReference, instance.type))
            else:
                type_ = self._as_uri_ref(dm.DirectRelationReference(instance.space, "Node"))

            yield id_, RDF.type, type_

            for view_id, properties in instance.properties.items():
                namespace = self._get_namespace(view_id.space)
                for key, value in properties.items():
                    for object_ in self._get_objects(value):
                        yield id_, namespace[key], object_
        else:
            raise NotImplementedError(f"Unknown instance type {type(instance)}")

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
        if self.overwrite_namespace:
            return self.overwrite_namespace
        if space not in self._namespace_by_space:
            self._namespace_by_space[space] = Namespace(space)
        return self._namespace_by_space[space]
