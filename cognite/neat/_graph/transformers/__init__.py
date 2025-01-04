from ._classic_cdf import (
    AddAssetDepth,
    AssetEventConnector,
    AssetFileConnector,
    AssetRelationshipConnector,
    AssetSequenceConnector,
    AssetTimeSeriesConnector,
    RelationshipAsEdgeTransformer,
)
from ._prune_graph import (
    AttachPropertyFromTargetToSource,
    PruneDanglingNodes,
    PruneDeadEndEdges,
    PruneInstancesOfUnknownType,
    PruneTypes,
)
from ._rdfpath import AddSelfReferenceProperty, MakeConnectionOnExactMatch
from ._value_type import ConnectionToLiteral, ConvertLiteral, LiteralToEntity, SplitMultiValueProperty

__all__ = [
    "AddAssetDepth",
    "AddSelfReferenceProperty",
    "AssetEventConnector",
    "AssetFileConnector",
    "AssetRelationshipConnector",
    "AssetSequenceConnector",
    "AssetTimeSeriesConnector",
    "AttachPropertyFromTargetToSource",
    "ConnectionToLiteral",
    "ConvertLiteral",
    "LiteralToEntity",
    "MakeConnectionOnExactMatch",
    "PruneDanglingNodes",
    "PruneDeadEndEdges",
    "PruneInstancesOfUnknownType",
    "PruneTypes",
    "RelationshipAsEdgeTransformer",
    "SplitMultiValueProperty",
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
    | PruneTypes
    | PruneDeadEndEdges
    | PruneInstancesOfUnknownType
    | ConvertLiteral
    | LiteralToEntity
    | ConnectionToLiteral
)
