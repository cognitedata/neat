import urllib.parse
import warnings
from abc import ABC
from collections.abc import Callable, Iterable, Iterator
from functools import lru_cache
from typing import cast

from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.query import ResultRow

from cognite.neat.v0.core._constants import CLASSIC_CDF_NAMESPACE, DEFAULT_NAMESPACE
from cognite.neat.v0.core._instances import extractors
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._issues.warnings import ResourceNotFoundWarning
from cognite.neat.v0.core._utils.collection_ import iterate_progress_bar
from cognite.neat.v0.core._utils.rdf_ import (
    Triple,
    add_triples_in_batch,
    get_namespace,
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

        row_output.add_triples.add(cast(Triple, (subject, DEFAULT_NAMESPACE.depth, object)))

        if self.depth_typing and (type_ := self.depth_typing.get(int(object), None)):
            row_output.remove_triples.add(cast(Triple, (subject, RDF.type, self.asset_type)))
            row_output.add_triples.add(cast(Triple, (subject, RDF.type, DEFAULT_NAMESPACE[type_])))

        row_output.instances_modified_count += 1

        return row_output


class BaseAssetConnector(BaseTransformerStandardised, ABC):
    description: str = "Connects assets to other cognite resources, thus forming bi-directional connection"
    _use_only_once: bool = True

    def _count_query(self) -> str:
        query = """SELECT (COUNT(?asset) as ?count)
                   WHERE {{
                        ?resource a <{resource_type}> .
                        ?resource <{connection}> ?asset .
                        ?asset a <{asset_type}> .
                        }}"""

        return query.format(
            asset_type=self.asset_type,
            resource_type=self.resource_type,
            connection=self.resource_to_asset_connection,
        )

    def _iterate_query(self) -> str:
        query = """SELECT ?asset ?resource
                   WHERE {{
                        ?resource a <{resource_type}> .
                        ?resource <{connection}> ?asset .
                        ?asset a <{asset_type}> .
                        }}"""

        return query.format(
            asset_type=self.asset_type,
            resource_type=self.resource_type,
            connection=self.resource_to_asset_connection,
        )

    def __init__(
        self,
        resource_to_asset_connection: URIRef,
        resource_type: URIRef,
        asset_to_resource_connection: URIRef | None = None,
        asset_type: URIRef | None = None,
    ) -> None:
        self.asset_type = asset_type or DEFAULT_NAMESPACE.Asset
        self.resource_to_asset_connection = resource_to_asset_connection
        self.resource_type = resource_type

        if asset_to_resource_connection:
            self.asset_to_resource_connection = asset_to_resource_connection
        else:
            namespace = Namespace(get_namespace(resource_type))
            type_ = remove_namespace_from_uri(resource_type)
            self.asset_to_resource_connection = namespace[type_[0].lower() + type_[1:]]

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()
        subject, object = query_result_row

        row_output.add_triples.add(cast(Triple, (subject, self.asset_to_resource_connection, object)))

        row_output.instances_modified_count += 1

        return row_output


class AssetTimeSeriesConnector(BaseAssetConnector):
    description: str = "Connects assets to timeseries, thus forming bi-directional connection"
    _need_changes = frozenset(
        {
            str(extractors.AssetsExtractor.__name__),
            str(extractors.TimeSeriesExtractor.__name__),
        }
    )

    def __init__(
        self,
        resource_to_asset_connection: URIRef | None = None,
        resource_type: URIRef | None = None,
        asset_to_resource_connection: URIRef | None = None,
        asset_type: URIRef | None = None,
    ):
        super().__init__(
            resource_to_asset_connection=resource_to_asset_connection or DEFAULT_NAMESPACE.assetId,
            resource_type=resource_type or DEFAULT_NAMESPACE.TimeSeries,
            asset_to_resource_connection=asset_to_resource_connection or DEFAULT_NAMESPACE.timeSeries,
            asset_type=asset_type or DEFAULT_NAMESPACE.Asset,
        )


class AssetSequenceConnector(BaseAssetConnector):
    description: str = "Connects assets to sequences, thus forming bi-directional connection"
    _need_changes = frozenset(
        {
            str(extractors.AssetsExtractor.__name__),
            str(extractors.SequencesExtractor.__name__),
        }
    )

    def __init__(
        self,
        resource_to_asset_connection: URIRef | None = None,
        resource_type: URIRef | None = None,
        asset_to_resource_connection: URIRef | None = None,
        asset_type: URIRef | None = None,
    ):
        super().__init__(
            resource_to_asset_connection=resource_to_asset_connection or DEFAULT_NAMESPACE.assetId,
            resource_type=resource_type or DEFAULT_NAMESPACE.Sequence,
            asset_to_resource_connection=asset_to_resource_connection or DEFAULT_NAMESPACE.sequence,
            asset_type=asset_type or DEFAULT_NAMESPACE.Asset,
        )


class AssetFileConnector(BaseAssetConnector):
    description: str = "Connects assets to files, thus forming bi-directional connection"
    _need_changes = frozenset(
        {
            str(extractors.AssetsExtractor.__name__),
            str(extractors.FilesExtractor.__name__),
        }
    )

    def __init__(
        self,
        resource_to_asset_connection: URIRef | None = None,
        resource_type: URIRef | None = None,
        asset_to_resource_connection: URIRef | None = None,
        asset_type: URIRef | None = None,
    ):
        super().__init__(
            resource_to_asset_connection=resource_to_asset_connection or DEFAULT_NAMESPACE.assetIds,
            resource_type=resource_type or DEFAULT_NAMESPACE.File,
            asset_to_resource_connection=asset_to_resource_connection or DEFAULT_NAMESPACE.file,
            asset_type=asset_type or DEFAULT_NAMESPACE.Asset,
        )


class AssetEventConnector(BaseAssetConnector):
    description: str = "Connects assets to events, thus forming bi-directional connection"
    _need_changes = frozenset(
        {
            str(extractors.AssetsExtractor.__name__),
            str(extractors.EventsExtractor.__name__),
        }
    )

    def __init__(
        self,
        resource_to_asset_connection: URIRef | None = None,
        resource_type: URIRef | None = None,
        asset_to_resource_connection: URIRef | None = None,
        asset_type: URIRef | None = None,
    ):
        super().__init__(
            resource_to_asset_connection=resource_to_asset_connection or DEFAULT_NAMESPACE.assetIds,
            resource_type=resource_type or DEFAULT_NAMESPACE.Event,
            asset_to_resource_connection=asset_to_resource_connection or DEFAULT_NAMESPACE.event,
            asset_type=asset_type or DEFAULT_NAMESPACE.Asset,
        )


class AssetRelationshipConnector(BaseTransformerStandardised):
    description: str = "Connects assets via relationships"
    _use_only_once: bool = True
    _need_changes = frozenset(
        {
            str(extractors.AssetsExtractor.__name__),
            str(extractors.RelationshipsExtractor.__name__),
        }
    )

    def _count_query(self) -> str:
        query = """SELECT (COUNT(?target_xid) as ?count) WHERE {{
                   ?relationship a <{relationship_type}> .
                   ?relationship <{relationship_source_xid_prop}> ?source_xid .
                   ?source_xid a <{asset_type}> .

                   ?relationship <{relationship_target_xid_prop}> ?target_xid .
                   ?target_xid a <{asset_type}> .}}"""

        return query.format(
            relationship_type=self.relationship_type,
            relationship_source_xid_prop=self.relationship_source_xid_prop,
            relationship_target_xid_prop=self.relationship_target_xid_prop,
            asset_type=self.asset_type,
        )

    def _iterate_query(self) -> str:
        query = """SELECT ?source_xid ?relationship ?target_xid WHERE {{
                   ?relationship a <{relationship_type}> .
                   ?relationship <{relationship_source_xid_prop}> ?source_xid .
                   ?source_xid a <{asset_type}> .

                   ?relationship <{relationship_target_xid_prop}> ?target_xid .
                   ?target_xid a <{asset_type}> .}}"""

        return query.format(
            relationship_type=self.relationship_type,
            relationship_source_xid_prop=self.relationship_source_xid_prop,
            relationship_target_xid_prop=self.relationship_target_xid_prop,
            asset_type=self.asset_type,
        )

    def __init__(
        self,
        asset_type: URIRef | None = None,
        relationship_type: URIRef | None = None,
        relationship_source_xid_prop: URIRef | None = None,
        relationship_target_xid_prop: URIRef | None = None,
    ):
        self.asset_type = asset_type or DEFAULT_NAMESPACE.Asset
        self.relationship_type = relationship_type or DEFAULT_NAMESPACE.Relationship
        self.relationship_source_xid_prop = relationship_source_xid_prop or DEFAULT_NAMESPACE.sourceExternalId
        self.relationship_target_xid_prop = relationship_target_xid_prop or DEFAULT_NAMESPACE.targetExternalId

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        row_output = RowTransformationOutput()
        source, relationship, target = query_result_row

        row_output.add_triples.add(cast(Triple, (source, DEFAULT_NAMESPACE.relationship, target)))
        row_output.add_triples.add(cast(Triple, (relationship, DEFAULT_NAMESPACE.source, source)))
        row_output.add_triples.add(cast(Triple, (relationship, DEFAULT_NAMESPACE.target, target)))

        row_output.remove_triples.add(cast(Triple, (relationship, self.relationship_source_xid_prop, None)))
        row_output.remove_triples.add(cast(Triple, (relationship, self.relationship_target_xid_prop, None)))

        row_output.instances_modified_count += 2

        return row_output


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
        edge_id = urllib.parse.quote(str(object_by_predicates["externalId"]))
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


class LookupRelationshipSourceTarget(BaseTransformerStandardised):
    """When relationships are extracted, the source and target are extracted as literals. This transformers
    lookup the externalID of the source and target and replaces the literals with the URIRef of the entity.
    """

    description = "Lookup relationships source and target externalId"
    _use_only_once: bool = True
    _need_changes = frozenset({extractors.RelationshipsExtractor.__name__})

    _lookup_entity_query = """SELECT ?entity
    WHERE {{
        ?entity a <{entity_type}> .
        ?entity <{namespace}externalId> "{external_id}" .
    }}"""

    def __init__(self, namespace: Namespace = CLASSIC_CDF_NAMESPACE, type_prefix: str | None = None) -> None:
        self._namespace = namespace
        self._type_prefix = type_prefix
        self._lookup_entity: Callable[[URIRef, str], URIRef] | None = None

    def _count_query(self) -> str:
        return f"""SELECT (COUNT(?instance) AS ?instanceCount)
WHERE {{
  ?instance a <{self._namespace}ClassicRelationship> .
}}"""

    def _iterate_query(self) -> str:
        return f"""SELECT ?instance ?source ?sourceType ?target ?targetType
        WHERE {{
          ?instance a <{self._namespace}ClassicRelationship> .
          ?instance <{self._namespace}sourceExternalId> ?source .
          ?instance <{self._namespace}targetExternalId> ?target .
          ?instance <{self._namespace}sourceType> ?sourceType .
          ?instance <{self._namespace}targetType> ?targetType
        }}"""

    def _iterator(self, graph: Graph) -> Iterator:
        self._lookup_entity = self.create_lookup_entity_with_external_id(graph, self._namespace, self._type_prefix)
        yield from graph.query(self._iterate_query())

    def operation(self, query_result_row: ResultRow) -> RowTransformationOutput:
        output = RowTransformationOutput()
        instance, source, source_type, target, target_type = cast(
            tuple[URIRef, Literal, URIRef, Literal, URIRef], query_result_row
        )
        if self._lookup_entity is None:
            raise NeatValueError(f"{type(self)}: .operation() called before .transform()")
        try:
            source_id = self._lookup_entity(source_type, source.toPython())
        except ValueError:
            warnings.warn(ResourceNotFoundWarning(source, "class", str(instance), "class"), stacklevel=2)
            return output

        try:
            target_id = self._lookup_entity(target_type, target.toPython())
        except ValueError:
            warnings.warn(ResourceNotFoundWarning(target, "class", str(instance), "class"), stacklevel=2)
            return output

        output.remove_triples.add((instance, self._namespace.sourceExternalId, source))
        output.remove_triples.add((instance, self._namespace.targetExternalId, target))
        output.add_triples.add((instance, self._namespace.sourceExternalId, source_id))
        output.add_triples.add((instance, self._namespace.targetExternalId, target_id))
        output.instances_modified_count += 1
        return output

    @staticmethod
    def create_lookup_entity_with_external_id(
        graph: Graph, namespace: Namespace, type_prefix: str | None
    ) -> Callable[[URIRef, str], URIRef]:
        @lru_cache(maxsize=10_000)
        def lookup_entity_with_external_id(entity_type: URIRef, external_id: str) -> URIRef:
            if type_prefix:
                entity_type = namespace[type_prefix + remove_namespace_from_uri(entity_type)]

            query = LookupRelationshipSourceTarget._lookup_entity_query.format(
                namespace=namespace, entity_type=entity_type, external_id=external_id
            )
            result = list(graph.query(query))
            if len(result) == 1:
                return cast(URIRef, result[0][0])  # type: ignore[index]
            raise ValueError(f"Could not find entity with external_id {external_id} and type {entity_type}")

        return lookup_entity_with_external_id
