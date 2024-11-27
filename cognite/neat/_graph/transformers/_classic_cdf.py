import textwrap
import warnings
from abc import ABC
from typing import cast

from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.query import ResultRow

from cognite.neat._constants import CLASSIC_CDF_NAMESPACE, DEFAULT_NAMESPACE
from cognite.neat._graph import extractors
from cognite.neat._issues.warnings import ResourceNotFoundWarning
from cognite.neat._utils.rdf_ import Triple, add_triples_in_batch, remove_namespace_from_uri

from ._base import BaseTransformer


class AddAssetDepth(BaseTransformer):
    description: str = "Adds depth of asset in the asset hierarchy to the graph"
    _use_only_once: bool = True
    _need_changes = frozenset({str(extractors.AssetsExtractor.__name__)})

    _parent_template: str = """SELECT ?child ?parent WHERE {{
                              <{asset_id}> <{parent_prop}> ?child .
                              OPTIONAL{{?child <{parent_prop}>+ ?parent .}}}}"""

    _root_template: str = """SELECT ?root WHERE {{
                             <{asset_id}> <{root_prop}> ?root .}}"""

    def __init__(
        self,
        asset_type: URIRef | None = None,
        root_prop: URIRef | None = None,
        parent_prop: URIRef | None = None,
        depth_typing: dict[int, str] | None = None,
    ):
        self.asset_type = asset_type or DEFAULT_NAMESPACE.Asset
        self.root_prop = root_prop or DEFAULT_NAMESPACE.rootId
        self.parent_prop = parent_prop or DEFAULT_NAMESPACE.parentId
        self.depth_typing = depth_typing

    def transform(self, graph: Graph) -> None:
        """Adds depth of asset in the asset hierarchy to the graph."""
        for result in graph.query(f"SELECT DISTINCT ?asset_id WHERE {{?asset_id a <{self.asset_type}>}}"):
            asset_id = cast(tuple, result)[0]
            if depth := self.get_depth(graph, asset_id, self.root_prop, self.parent_prop):
                graph.add((asset_id, DEFAULT_NAMESPACE.depth, Literal(depth)))

                if self.depth_typing and (type_ := self.depth_typing.get(depth, None)):
                    # remove existing type
                    graph.remove((asset_id, RDF.type, None))

                    # add new type
                    graph.add((asset_id, RDF.type, DEFAULT_NAMESPACE[type_]))

    @classmethod
    def get_depth(
        cls,
        graph: Graph,
        asset_id: URIRef,
        root_prop: URIRef,
        parent_prop: URIRef,
    ) -> int | None:
        """Get asset depth in the asset hierarchy."""

        # Handles non-root assets
        if result := list(graph.query(cls._parent_template.format(asset_id=asset_id, parent_prop=parent_prop))):
            return len(cast(list[tuple], result)) + 2 if cast(list[tuple], result)[0][1] else 2

        # Handles root assets
        elif (
            (result := list(graph.query(cls._root_template.format(asset_id=asset_id, root_prop=root_prop))))
            and len(cast(list[tuple], result)) == 1
            and cast(list[tuple], result)[0][0] == asset_id
        ):
            return 1
        else:
            return None


class BaseAssetConnector(BaseTransformer, ABC):
    _asset_type: URIRef = DEFAULT_NAMESPACE.Asset
    _item_type: URIRef
    _default_attribute: URIRef
    _connection_type: URIRef

    _select_item_ids = "SELECT DISTINCT ?item_id WHERE {{?item_id a <{item_type}>}}"
    _select_connected_assets: str = textwrap.dedent("""SELECT ?asset_id WHERE {{
                              <{item_id}> <{attribute}> ?asset_id .
                              ?asset_id a <{asset_type}>}}""")

    def __init__(self, attribute: URIRef | None = None) -> None:
        self._attribute = attribute or self._default_attribute

    def transform(self, graph: Graph) -> None:
        for item_id, *_ in graph.query(self._select_item_ids.format(item_type=self._item_type)):  # type: ignore[misc]
            triples: list[Triple] = []
            for asset_id, *_ in graph.query(  # type: ignore[misc]
                self._select_connected_assets.format(
                    item_id=item_id, attribute=self._attribute, asset_type=self._asset_type
                )
            ):
                triples.append((asset_id, self._connection_type, item_id))  # type: ignore[arg-type]
            add_triples_in_batch(graph, triples)


class AssetTimeSeriesConnector(BaseAssetConnector):
    description: str = "Connects assets to timeseries, thus forming bi-directional connection"
    _use_only_once: bool = True
    _need_changes = frozenset(
        {
            str(extractors.AssetsExtractor.__name__),
            str(extractors.TimeSeriesExtractor.__name__),
        }
    )
    _item_type = DEFAULT_NAMESPACE.TimeSeries
    _default_attribute = DEFAULT_NAMESPACE.assetId
    _connection_type = DEFAULT_NAMESPACE.timeSeries


class AssetSequenceConnector(BaseAssetConnector):
    description: str = "Connects assets to sequences, thus forming bi-directional connection"
    _use_only_once: bool = True
    _need_changes = frozenset(
        {
            str(extractors.AssetsExtractor.__name__),
            str(extractors.SequencesExtractor.__name__),
        }
    )
    _item_type = DEFAULT_NAMESPACE.Sequence
    _default_attribute = DEFAULT_NAMESPACE.assetId
    _connection_type = DEFAULT_NAMESPACE.sequence


class AssetFileConnector(BaseAssetConnector):
    description: str = "Connects assets to files, thus forming bi-directional connection"
    _use_only_once: bool = True
    _need_changes = frozenset(
        {
            str(extractors.AssetsExtractor.__name__),
            str(extractors.FilesExtractor.__name__),
        }
    )
    _item_type = DEFAULT_NAMESPACE.File
    _default_attribute = DEFAULT_NAMESPACE.assetIds
    _connection_type = DEFAULT_NAMESPACE.file


class AssetEventConnector(BaseAssetConnector):
    description: str = "Connects assets to events, thus forming bi-directional connection"
    _use_only_once: bool = True
    _need_changes = frozenset(
        {
            str(extractors.AssetsExtractor.__name__),
            str(extractors.EventsExtractor.__name__),
        }
    )
    _item_type = DEFAULT_NAMESPACE.Event
    _default_attribute = DEFAULT_NAMESPACE.assetIds
    _connection_type = DEFAULT_NAMESPACE.event


class AssetRelationshipConnector(BaseTransformer):
    description: str = "Connects assets via relationships"
    _use_only_once: bool = True
    _need_changes = frozenset(
        {
            str(extractors.AssetsExtractor.__name__),
            str(extractors.RelationshipsExtractor.__name__),
        }
    )
    _asset_template: str = """SELECT ?source ?target WHERE {{
                              <{relationship_id}> <{relationship_source_xid_prop}> ?source_xid .
                              ?source <{asset_xid_property}> ?source_xid .
                              ?source a <{asset_type}> .

                              <{relationship_id}> <{relationship_target_xid_prop}> ?target_xid .
                              ?target <{asset_xid_property}> ?target_xid .
                              ?target a <{asset_type}> .}}"""

    def __init__(
        self,
        asset_type: URIRef | None = None,
        relationship_type: URIRef | None = None,
        relationship_source_xid_prop: URIRef | None = None,
        relationship_target_xid_prop: URIRef | None = None,
        asset_xid_property: URIRef | None = None,
    ):
        self.asset_type = asset_type or DEFAULT_NAMESPACE.Asset
        self.relationship_type = relationship_type or DEFAULT_NAMESPACE.Relationship
        self.relationship_source_xid_prop = relationship_source_xid_prop or DEFAULT_NAMESPACE.sourceExternalId
        self.relationship_target_xid_prop = relationship_target_xid_prop or DEFAULT_NAMESPACE.targetExternalId
        self.asset_xid_property = asset_xid_property or DEFAULT_NAMESPACE.externalId

    def transform(self, graph: Graph) -> None:
        for relationship_id_result in graph.query(
            f"SELECT DISTINCT ?relationship_id WHERE {{?relationship_id a <{self.relationship_type}>}}"
        ):
            relationship_id: URIRef = cast(tuple, relationship_id_result)[0]

            if assets_id_res := list(
                graph.query(
                    self._asset_template.format(
                        relationship_id=relationship_id,
                        asset_xid_property=self.asset_xid_property,
                        relationship_source_xid_prop=self.relationship_source_xid_prop,
                        relationship_target_xid_prop=self.relationship_target_xid_prop,
                        asset_type=self.asset_type,
                    )
                )
            ):
                # files can be connected to multiple assets in the graph
                for source_asset_id, target_asset_id in cast(list[tuple], assets_id_res):
                    # create a relationship between the two assets
                    graph.add(
                        (
                            source_asset_id,
                            DEFAULT_NAMESPACE.relationship,
                            relationship_id,
                        )
                    )
                    graph.add(
                        (
                            target_asset_id,
                            DEFAULT_NAMESPACE.relationship,
                            relationship_id,
                        )
                    )

                    # add source and target to the relationship
                    graph.add((relationship_id, DEFAULT_NAMESPACE.source, source_asset_id))
                    graph.add((relationship_id, DEFAULT_NAMESPACE.target, target_asset_id))

                    # remove properties that are not needed, specifically the external ids
                    graph.remove((relationship_id, self.relationship_source_xid_prop, None))
                    graph.remove((relationship_id, self.relationship_target_xid_prop, None))


class RelationshipToSchemaTransformer(BaseTransformer):
    """Replaces relationships with a schema.

    This transformer analyzes the relationships in the graph and modifies them to be part of the schema
    for Assets, Events, Files, Sequences, and TimeSeries. Relationships without any properties
    are replaced by a simple relationship between the source and target nodes. Relationships with
    properties are replaced by a schema that contains the properties as attributes.

    Args:
        limit: The minimum number of relationships that need to be present for it
            to be converted into a schema. Default is 1.

    """

    def __init__(self, limit: int = 1, namespace: Namespace = CLASSIC_CDF_NAMESPACE) -> None:
        self._limit = limit
        self._namespace = namespace

    _NOT_PROPERTIES: frozenset[str] = frozenset(
        {"sourceExternalId", "targetExternalId", "externalId", "sourceType", "targetType"}
    )
    _RELATIONSHIP_NODE_TYPES: tuple[str, ...] = tuple(["Asset", "Event", "File", "Sequence", "TimeSeries"])
    description = "Replaces relationships with a schema"
    _use_only_once: bool = True
    _need_changes = frozenset({str(extractors.RelationshipsExtractor.__name__)})

    _count_by_source_target = """PREFIX classic: <{namespace}>

SELECT (COUNT(?instance) AS ?instanceCount)
WHERE {{
  ?instance a classic:Relationship .
  ?instance classic:sourceType classic:{source_type} .
  ?instance classic:targetType classic:{target_type} .
}}"""

    _instances = """PREFIX classic: <{namespace}>

SELECT ?instance
WHERE {{
    ?instance a classic:Relationship .
    ?instance classic:sourceType classic:{source_type} .
    ?instance classic:targetType classic:{target_type} .
}}"""
    _lookup_entity_query = """PREFIX classic: <{namespace}>

SELECT ?entity
WHERE {{
    ?entity a classic:{entity_type} .
    ?entity classic:externalId "{external_id}" .
}}"""

    def transform(self, graph: Graph) -> None:
        for source_type in self._RELATIONSHIP_NODE_TYPES:
            for target_type in self._RELATIONSHIP_NODE_TYPES:
                query = self._count_by_source_target.format(
                    namespace=self._namespace, source_type=source_type, target_type=target_type
                )
                for instance_count in graph.query(query):
                    if int(instance_count[0]) < self._limit:  # type: ignore[index, arg-type]
                        continue
                    query = self._instances.format(
                        namespace=self._namespace, source_type=source_type, target_type=target_type
                    )
                    for result in graph.query(query):
                        instance_id = cast(URIRef, result[0])  # type: ignore[index, misc]
                        self._convert_relationship_to_schema(graph, instance_id, source_type, target_type)

    def _convert_relationship_to_schema(
        self, graph: Graph, instance_id: URIRef, source_type: str, target_type: str
    ) -> None:
        result = cast(list[ResultRow], list(graph.query(f"DESCRIBE <{instance_id}>")))
        object_by_predicates = cast(
            dict[str, URIRef | Literal], {remove_namespace_from_uri(row[1]): row[2] for row in result}
        )
        source_external_id = cast(URIRef, object_by_predicates["sourceExternalId"])
        target_source_id = cast(URIRef, object_by_predicates["targetExternalId"])
        try:
            source_id = self._lookup_entity(graph, source_type, source_external_id)
        except ValueError:
            warnings.warn(ResourceNotFoundWarning(source_external_id, "class", str(instance_id), "class"), stacklevel=2)
            return None
        try:
            target_id = self._lookup_entity(graph, target_type, target_source_id)
        except ValueError:
            warnings.warn(ResourceNotFoundWarning(target_source_id, "class", str(instance_id), "class"), stacklevel=2)
            return None
        external_id = str(object_by_predicates["externalId"])
        # If there is properties on the relationship, we create a new intermediate node
        self._create_node(graph, object_by_predicates, external_id, source_id, target_id, self._predicate(target_type))

        for triple in result:
            graph.remove(triple)  # type: ignore[arg-type]

    def _lookup_entity(self, graph: Graph, entity_type: str, external_id: str) -> URIRef:
        query = self._lookup_entity_query.format(
            namespace=self._namespace, entity_type=entity_type, external_id=external_id
        )
        result = list(graph.query(query))
        if len(result) == 1:
            return cast(URIRef, result[0][0])  # type: ignore[index]
        raise ValueError(f"Could not find entity with external_id {external_id} and type {entity_type}")

    def _create_node(
        self,
        graph: Graph,
        objects_by_predicates: dict[str, URIRef | Literal],
        external_id: str,
        source_id: URIRef,
        target_id: URIRef,
        predicate: URIRef,
    ) -> None:
        """Creates a new intermediate node for the relationship with properties."""
        # Create the entity with the properties
        instance_id = self._namespace[external_id]
        graph.add((instance_id, RDF.type, self._namespace["Edge"]))
        for prop_name, object_ in objects_by_predicates.items():
            if prop_name in self._NOT_PROPERTIES:
                continue
            graph.add((instance_id, self._namespace[prop_name], object_))

        # Target and Source IDs will always be a combination of Asset, Sequence, Event, TimeSeries, and File.
        # If we assume source ID is an asset and target ID is a time series, then
        # before we had relationship pointing to both: timeseries <- relationship -> asset
        # After, we want asset -> timeseries, and asset.edgeSource -> Edge
        # and the new edge will point to the asset and the timeseries through startNode and endNode

        # Link the two entities directly,
        graph.add((source_id, predicate, target_id))
        # Create the new edge
        graph.add((instance_id, self._namespace["startNode"], source_id))
        graph.add((instance_id, self._namespace["endNode"], target_id))

        # Link the source to the edge properties
        graph.add((source_id, self._namespace["edgeSource"], instance_id))

    def _predicate(self, target_type: str) -> URIRef:
        return self._namespace[f"relationship{target_type.capitalize()}"]
