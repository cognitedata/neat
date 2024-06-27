from typing import cast

from rdflib import Graph, Literal, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph import extractors

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
        self, asset_type: URIRef | None = None, root_prop: URIRef | None = None, parent_prop: URIRef | None = None
    ):
        self.asset_type = asset_type or DEFAULT_NAMESPACE.Asset
        self.root_prop = root_prop or DEFAULT_NAMESPACE.root
        self.parent_prop = parent_prop or DEFAULT_NAMESPACE.parent

    def transform(self, graph: Graph) -> None:
        """Adds depth of asset in the asset hierarchy to the graph."""
        for result in graph.query(f"SELECT DISTINCT ?asset_id WHERE {{?asset_id a <{self.asset_type}>}}"):
            asset_id = cast(tuple, result)[0]
            if depth := self.get_depth(graph, asset_id, self.root_prop, self.parent_prop):
                graph.add((asset_id, DEFAULT_NAMESPACE.depth, Literal(depth)))

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


class AssetTimeSeriesConnector(BaseTransformer):
    description: str = "Connects assets to timeseries, thus forming bi-directional connection"
    _use_only_once: bool = True
    _need_changes = frozenset({str(extractors.AssetsExtractor.__name__), str(extractors.TimeSeriesExtractor.__name__)})
    _asset_template: str = """SELECT ?asset_id WHERE {{
                              <{timeseries_id}> <{asset_prop}> ?asset_id .
                              ?asset_id a <{asset_type}>}}"""

    def __init__(
        self,
        asset_type: URIRef | None = None,
        timeseries_type: URIRef | None = None,
        asset_prop: URIRef | None = None,
    ):
        self.asset_type = asset_type or DEFAULT_NAMESPACE.Asset
        self.timeseries_type = timeseries_type or DEFAULT_NAMESPACE.TimeSeries
        self.asset_prop = asset_prop or DEFAULT_NAMESPACE.asset

    def transform(self, graph: Graph) -> None:
        for ts_id_result in graph.query(
            f"SELECT DISTINCT ?timeseries_id WHERE {{?timeseries_id a <{self.timeseries_type}>}}"
        ):
            timeseries_id: URIRef = cast(tuple, ts_id_result)[0]

            if asset_id_res := list(
                graph.query(
                    self._asset_template.format(
                        timeseries_id=timeseries_id,
                        asset_prop=self.asset_prop,
                        asset_type=self.asset_type,
                    )
                )
            ):
                # timeseries can be connected to only one asset in the graph
                asset_id = cast(list[tuple], asset_id_res)[0][0]
                graph.add((asset_id, DEFAULT_NAMESPACE.timeSeries, timeseries_id))


class AssetSequenceConnector(BaseTransformer):
    description: str = "Connects assets to sequences, thus forming bi-directional connection"
    _use_only_once: bool = True
    _need_changes = frozenset({str(extractors.AssetsExtractor.__name__), str(extractors.SequencesExtractor.__name__)})
    _asset_template: str = """SELECT ?asset_id WHERE {{
                              <{sequence_id}> <{asset_prop}> ?asset_id .
                              ?asset_id a <{asset_type}>}}"""

    def __init__(
        self,
        asset_type: URIRef | None = None,
        sequence_type: URIRef | None = None,
        asset_prop: URIRef | None = None,
    ):
        self.asset_type = asset_type or DEFAULT_NAMESPACE.Asset
        self.sequence_type = sequence_type or DEFAULT_NAMESPACE.Sequence
        self.asset_prop = asset_prop or DEFAULT_NAMESPACE.asset

    def transform(self, graph: Graph) -> None:
        for sequency_id_result in graph.query(
            f"SELECT DISTINCT ?sequence_id WHERE {{?sequence_id a <{self.sequence_type}>}}"
        ):
            sequence_id: URIRef = cast(tuple, sequency_id_result)[0]

            if asset_id_res := list(
                graph.query(
                    self._asset_template.format(
                        sequence_id=sequence_id,
                        asset_prop=self.asset_prop,
                        asset_type=self.asset_type,
                    )
                )
            ):
                # sequence can be connected to only one asset in the graph
                asset_id = cast(list[tuple], asset_id_res)[0][0]
                graph.add((asset_id, DEFAULT_NAMESPACE.sequence, sequence_id))


class AssetFileConnector(BaseTransformer):
    description: str = "Connects assets to files, thus forming bi-directional connection"
    _use_only_once: bool = True
    _need_changes = frozenset({str(extractors.AssetsExtractor.__name__), str(extractors.FilesExtractor.__name__)})
    _asset_template: str = """SELECT ?asset_id WHERE {{
                              <{file_id}> <{asset_prop}> ?asset_id .
                              ?asset_id a <{asset_type}>}}"""

    def __init__(
        self,
        asset_type: URIRef | None = None,
        file_type: URIRef | None = None,
        asset_prop: URIRef | None = None,
    ):
        self.asset_type = asset_type or DEFAULT_NAMESPACE.Asset
        self.file_type = file_type or DEFAULT_NAMESPACE.File
        self.asset_prop = asset_prop or DEFAULT_NAMESPACE.asset

    def transform(self, graph: Graph) -> None:
        for sequency_id_result in graph.query(f"SELECT DISTINCT ?file_id WHERE {{?file_id a <{self.file_type}>}}"):
            file_id: URIRef = cast(tuple, sequency_id_result)[0]

            if assets_id_res := list(
                graph.query(
                    self._asset_template.format(
                        file_id=file_id,
                        asset_prop=self.asset_prop,
                        asset_type=self.asset_type,
                    )
                )
            ):
                # files can be connected to multiple assets in the graph
                for (asset_id,) in cast(list[tuple], assets_id_res):
                    graph.add((asset_id, DEFAULT_NAMESPACE.file, file_id))


class AssetEventConnector(BaseTransformer):
    description: str = "Connects assets to events, thus forming bi-directional connection"
    _use_only_once: bool = True
    _need_changes = frozenset({str(extractors.AssetsExtractor.__name__), str(extractors.EventsExtractor.__name__)})
    _asset_template: str = """SELECT ?asset_id WHERE {{
                              <{event_id}> <{asset_prop}> ?asset_id .
                              ?asset_id a <{asset_type}>}}"""

    def __init__(
        self,
        asset_type: URIRef | None = None,
        event_type: URIRef | None = None,
        asset_prop: URIRef | None = None,
    ):
        self.asset_type = asset_type or DEFAULT_NAMESPACE.Asset
        self.event_type = event_type or DEFAULT_NAMESPACE.Event
        self.asset_prop = asset_prop or DEFAULT_NAMESPACE.asset

    def transform(self, graph: Graph) -> None:
        for event_id_result in graph.query(f"SELECT DISTINCT ?event_id WHERE {{?event_id a <{self.event_type}>}}"):
            event_id: URIRef = cast(tuple, event_id_result)[0]

            if assets_id_res := list(
                graph.query(
                    self._asset_template.format(
                        event_id=event_id,
                        asset_prop=self.asset_prop,
                        asset_type=self.asset_type,
                    )
                )
            ):
                # files can be connected to multiple assets in the graph
                for (asset_id,) in cast(list[tuple], assets_id_res):
                    graph.add((asset_id, DEFAULT_NAMESPACE.event, event_id))


class AssetRelationshipConnector(BaseTransformer):
    description: str = "Connects assets via relationships"
    _use_only_once: bool = True
    _need_changes = frozenset(
        {str(extractors.AssetsExtractor.__name__), str(extractors.RelationshipsExtractor.__name__)}
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
        self.relationship_source_xid_prop = relationship_source_xid_prop or DEFAULT_NAMESPACE.source_external_id
        self.relationship_target_xid_prop = relationship_target_xid_prop or DEFAULT_NAMESPACE.target_external_id
        self.asset_xid_property = asset_xid_property or DEFAULT_NAMESPACE.external_id

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
                    graph.add((source_asset_id, DEFAULT_NAMESPACE.relationship, relationship_id))
                    graph.add((target_asset_id, DEFAULT_NAMESPACE.relationship, relationship_id))

                    # add source and target to the relationship
                    graph.add((relationship_id, DEFAULT_NAMESPACE.source, source_asset_id))
                    graph.add((relationship_id, DEFAULT_NAMESPACE.target, target_asset_id))

                    # remove properties that are not needed, specifically the external ids
                    graph.remove((relationship_id, self.relationship_source_xid_prop, None))
                    graph.remove((relationship_id, self.relationship_target_xid_prop, None))
