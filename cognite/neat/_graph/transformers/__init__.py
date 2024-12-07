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
from ._value_type import ConvertLiteral, LiteralToEntity, SplitMultiValueProperty

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
    "ConvertLiteral",
    "LiteralToEntity",
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
    | ConvertLiteral
    | LiteralToEntity
)
