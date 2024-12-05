from ._classic_cdf import (
    AddAssetDepth,
    AssetEventConnector,
    AssetFileConnector,
    AssetRelationshipConnector,
    AssetSequenceConnector,
    AssetTimeSeriesConnector,
    RelationshipAsEdgeTransformer,
)
from ._prune_graph import AttachPropertyFromTargetToSource, PruneDanglingNodes
from ._rdfpath import AddSelfReferenceProperty, MakeConnectionOnExactMatch
from ._value_type import SplitMultiValueProperty

__all__ = [
    "AddAssetDepth",
    "AssetTimeSeriesConnector",
    "AssetSequenceConnector",
    "AssetFileConnector",
    "AssetEventConnector",
    "AssetRelationshipConnector",
    "AddSelfReferenceProperty",
    "SplitMultiValueProperty",
    "RelationshipAsEdgeTransformer",
    "MakeConnectionOnExactMatch",
    "AttachPropertyFromTargetToSource",
    "PruneDanglingNodes",
]

Transformers = (
    AddAssetDepth
    | AssetTimeSeriesConnector
    | AssetSequenceConnector
    | AssetFileConnector
    | AssetEventConnector
    | AssetRelationshipConnector
    | AddSelfReferenceProperty
    | SplitMultiValueProperty
    | RelationshipAsEdgeTransformer
    | MakeConnectionOnExactMatch
    | AttachPropertyFromTargetToSource
    | PruneDanglingNodes
)
