from typing import ClassVar, cast

from rdflib import Graph, Literal, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors import AssetsExtractor

from ._base import BaseTransformer


class AddAssetDepth(BaseTransformer):
    description: str = "Adds depth of asset in the asset hierarchy to the graph"
    _use_only_once: bool = True
    _need_changes: ClassVar[tuple] = (AssetsExtractor.__name__,)

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
        if res := list(graph.query(cls._parent_template.format(asset_id=asset_id, parent_prop=parent_prop))):
            return len(cast(list[tuple], res)) + 2 if cast(list[tuple], res)[0][1] else 2

        # Handles root assets
        elif (
            (res := list(graph.query(cls._root_template.format(asset_id=asset_id, root_prop=root_prop))))
            and len(cast(list[tuple], res)) == 1
            and cast(list[tuple], res)[0][0] == asset_id
        ):
            return 1
        else:
            return None
