import textwrap
import warnings
from abc import ABC
from collections.abc import Callable, Iterable
from functools import lru_cache
from typing import cast

from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.query import ResultRow

from cognite.neat._constants import CLASSIC_CDF_NAMESPACE, DEFAULT_NAMESPACE
from cognite.neat._graph import extractors
from cognite.neat._issues.warnings import ResourceNotFoundWarning
from cognite.neat._utils.collection_ import iterate_progress_bar
from cognite.neat._utils.rdf_ import (
    Triple,
    add_triples_in_batch,
    remove_instance_ids_in_batch,
    remove_namespace_from_uri,
)

from ._base import BaseTransformer, BaseTransformerStandardised, RowTransformationOutput


class AddAssetDepth(BaseTransformerStandardised):
    description: str = "Adds depth of asset in the asset hierarchy and optionally types asset based on depth"
    _use_only_once: bool = True
    _need_changes = frozenset({str(extractors.AssetsExtractor.__name__)})

    def __init__(
        self,
        asset_type: URIRef | None = None,
        parent_prop: URIRef | None = None,
        depth_typing: dict[int, str] | None = None,
    ):
        self.asset_type = asset_type or DEFAULT_NAMESPACE.Asset
        self.parent_prop = parent_prop or DEFAULT_NAMESPACE.parentId
        self.depth_typing = depth_typing

    def _iterate_query(self) -> str:
        query = """SELECT ?asset (IF(?isRoot, 0, COUNT(?parent)) AS ?parentCount)
                   WHERE {{
                        ?asset a <{asset_type}> .
                        OPTIONAL {{ ?asset <{parent_prop}>+ ?parent . }}
                        BIND(IF(BOUND(?parent), false, true) AS ?isRoot)}}
                   GROUP BY ?asset ?isRoot
                   ORDER BY DESC(?parentCount)"""

        return query.format(
            asset_type=self.asset_type,
            parent_prop=self.parent_prop,
        )

    def _count_query(self) -> str:
        query = """SELECT (COUNT(?asset) as ?count)
                   WHERE {{ ?asset a <{asset_type}> . }}"""

        return query.format(asset_type=self.asset_type)

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()
        subject, object = query_result_row

        row_output.add_triples.append(cast(Triple, (subject, DEFAULT_NAMESPACE.depth, object)))

        if self.depth_typing and (type_ := self.depth_typing.get(int(object), None)):
            row_output.remove_triples.append(cast(Triple, (subject, RDF.type, self.asset_type)))
            row_output.add_triples.append(cast(Triple, (subject, RDF.type, DEFAULT_NAMESPACE[type_])))

        row_output.instances_modified_count += 1

        return row_output


# TODO: standardise
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


# TODO: standardise
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


# TODO: standardise
class RelationshipAsEdgeTransformer(BaseTransformer):
    """Converts relationships into edges in the graph.

    This transformer converts relationships into edges in the graph. This is useful as the
    edges will be picked up as part of the schema connected to Assets, Events, Files, Sequenses,
    and TimeSeries in the InferenceImporter.

    Args:
        min_relationship_types: The minimum number of relationship types that must exists to convert those
            relationships to edges. For example, if there is only 5 relationships between Assets and TimeSeries,
            and limit is 10, those relationships will not be converted to edges.
        limit_per_type: The number of conversions to perform per relationship type. For example, if there are 10
            relationships between Assets and TimeSeries, and limit_per_type is 1, only 1 of those relationships
            will be converted to an edge. If None, all relationships will be converted.

    """

    def __init__(
        self,
        min_relationship_types: int = 1,
        limit_per_type: int | None = None,
        namespace: Namespace = CLASSIC_CDF_NAMESPACE,
    ) -> None:
        self._min_relationship_types = min_relationship_types
        self._limit_per_type = limit_per_type
        self._namespace = namespace

    _NOT_PROPERTIES: frozenset[str] = frozenset(
        {"sourceExternalId", "targetExternalId", "externalId", "sourceType", "targetType"}
    )
    _RELATIONSHIP_NODE_TYPES: tuple[str, ...] = tuple(["Asset", "Event", "File", "Sequence", "TimeSeries"])
    description = "Converts relationships to edge"
    _use_only_once: bool = True
    _need_changes = frozenset({extractors.RelationshipsExtractor.__name__})

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

    @staticmethod
    def create_lookup_entity_with_external_id(graph: Graph, namespace: Namespace) -> Callable[[str, str], URIRef]:
        @lru_cache(maxsize=10_000)
        def lookup_entity_with_external_id(entity_type: str, external_id: str) -> URIRef:
            query = RelationshipAsEdgeTransformer._lookup_entity_query.format(
                namespace=namespace, entity_type=entity_type, external_id=external_id
            )
            result = list(graph.query(query))
            if len(result) == 1:
                return cast(URIRef, result[0][0])  # type: ignore[index]
            raise ValueError(f"Could not find entity with external_id {external_id} and type {entity_type}")

        return lookup_entity_with_external_id

    def transform(self, graph: Graph) -> None:
        lookup_entity_with_external_id = self.create_lookup_entity_with_external_id(graph, self._namespace)
        for source_type in self._RELATIONSHIP_NODE_TYPES:
            for target_type in self._RELATIONSHIP_NODE_TYPES:
                query = self._count_by_source_target.format(
                    namespace=self._namespace, source_type=source_type, target_type=target_type
                )
                for instance_count_res in graph.query(query):
                    instance_count = int(instance_count_res[0])  # type: ignore[index, arg-type]
                    if instance_count < self._min_relationship_types:
                        continue
                    edge_triples = self._edge_triples(
                        graph, source_type, target_type, instance_count, lookup_entity_with_external_id
                    )
                    add_triples_in_batch(graph, edge_triples)

    def _edge_triples(
        self,
        graph: Graph,
        source_type: str,
        target_type: str,
        instance_count: int,
        lookup_entity_with_external_id: Callable[[str, str], URIRef],
    ) -> Iterable[Triple]:
        query = self._instances.format(namespace=self._namespace, source_type=source_type, target_type=target_type)
        total_instance_count = instance_count if self._limit_per_type is None else self._limit_per_type

        converted_relationships: list[URIRef] = []
        for no, result in enumerate(
            iterate_progress_bar(graph.query(query), total=total_instance_count, description="Relationships to edges")
        ):
            if self._limit_per_type is not None and no >= self._limit_per_type:
                break
            relationship_id = cast(URIRef, result[0])  # type: ignore[index, misc]
            yield from self._relationship_as_edge(
                graph, relationship_id, source_type, target_type, lookup_entity_with_external_id
            )
            converted_relationships.append(relationship_id)

            if len(converted_relationships) >= 1_000:
                remove_instance_ids_in_batch(graph, converted_relationships)
                converted_relationships = []

        remove_instance_ids_in_batch(graph, converted_relationships)

    def _relationship_as_edge(
        self,
        graph: Graph,
        relationship_id: URIRef,
        source_type: str,
        target_type: str,
        lookup_entity_with_external_id: Callable[[str, str], URIRef],
    ) -> list[Triple]:
        relationship_triples = cast(list[Triple], list(graph.query(f"DESCRIBE <{relationship_id}>")))
        object_by_predicates = cast(
            dict[str, URIRef | Literal],
            {remove_namespace_from_uri(row[1]): row[2] for row in relationship_triples if row[1] != RDF.type},
        )
        source_external_id = cast(URIRef, object_by_predicates["sourceExternalId"])
        target_source_id = cast(URIRef, object_by_predicates["targetExternalId"])
        try:
            source_id = lookup_entity_with_external_id(source_type, source_external_id)
        except ValueError:
            warnings.warn(
                ResourceNotFoundWarning(source_external_id, "class", str(relationship_id), "class"), stacklevel=2
            )
            return []
        try:
            target_id = lookup_entity_with_external_id(target_type, target_source_id)
        except ValueError:
            warnings.warn(
                ResourceNotFoundWarning(target_source_id, "class", str(relationship_id), "class"), stacklevel=2
            )
            return []
        edge_id = str(object_by_predicates["externalId"])
        # If there is properties on the relationship, we create a new intermediate node
        edge_type = self._namespace[f"{source_type}To{target_type}Edge"]
        return self._create_edge(
            object_by_predicates, edge_id, source_id, target_id, self._predicate(target_type), edge_type
        )

    def _lookup_entity(self, graph: Graph, entity_type: str, external_id: str) -> URIRef:
        query = self._lookup_entity_query.format(
            namespace=self._namespace, entity_type=entity_type, external_id=external_id
        )
        result = list(graph.query(query))
        if len(result) == 1:
            return cast(URIRef, result[0][0])  # type: ignore[index]
        raise ValueError(f"Could not find entity with external_id {external_id} and type {entity_type}")

    def _create_edge(
        self,
        objects_by_predicates: dict[str, URIRef | Literal],
        external_id: str,
        source_id: URIRef,
        target_id: URIRef,
        predicate: URIRef,
        edge_type: URIRef,
    ) -> list[Triple]:
        """Creates a new intermediate node for the relationship with properties."""
        # Create the entity with the properties
        edge_triples: list[Triple] = []
        edge_id = self._namespace[external_id]

        edge_triples.append((edge_id, RDF.type, edge_type))
        for prop_name, object_ in objects_by_predicates.items():
            if prop_name in self._NOT_PROPERTIES:
                continue
            edge_triples.append((edge_id, self._namespace[prop_name], object_))

        # Target and Source IDs will always be a combination of Asset, Sequence, Event, TimeSeries, and File.
        # If we assume source ID is an asset and target ID is a time series, then
        # before we had relationship pointing to both: timeseries <- relationship -> asset
        # After, we want asset <-> Edge -> TimeSeries
        # and the new edge will point to the asset and the timeseries through startNode and endNode

        # Link the source to the new edge
        edge_triples.append((source_id, predicate, edge_id))
        # Link the edge to the source and target
        edge_triples.append((edge_id, self._namespace["startNode"], source_id))
        edge_triples.append((edge_id, self._namespace["endNode"], target_id))
        return edge_triples

    def _predicate(self, target_type: str) -> URIRef:
        return self._namespace[f"relationship{target_type.capitalize()}"]
