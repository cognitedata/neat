from ._base import BaseTransformerStandardised
from ._classic_cdf import (
    AddAssetDepth,
    AssetEventConnector,
    AssetFileConnector,
    AssetRelationshipConnector,
    AssetSequenceConnector,
    AssetTimeSeriesConnector,
    LookupRelationshipSourceTarget,
    RelationshipAsEdgeTransformer,
)
from ._prune_graph import (
    AttachPropertyFromTargetToSource,
    PruneDanglingNodes,
    PruneDeadEndEdges,
    PruneInstancesOfUnknownType,
    PruneTypes,
)
from ._rdfpath import MakeConnectionOnExactMatch
from ._value_type import ConnectionToLiteral, ConvertLiteral, LiteralToEntity, SetType, SplitMultiValueProperty

__all__ = [
    "AddAssetDepth",
    "AssetEventConnector",
    "AssetFileConnector",
    "AssetRelationshipConnector",
    "AssetSequenceConnector",
    "AssetTimeSeriesConnector",
    "AttachPropertyFromTargetToSource",
    "ConnectionToLiteral",
    "ConvertLiteral",
    "LiteralToEntity",
    "LookupRelationshipSourceTarget",
    "MakeConnectionOnExactMatch",
    "PruneDanglingNodes",
    "PruneDeadEndEdges",
    "PruneInstancesOfUnknownType",
    "PruneTypes",
    "RelationshipAsEdgeTransformer",
    "SetType",
    "SplitMultiValueProperty",
]

Transformers = (
    AddAssetDepth
    | AssetTimeSeriesConnector
    | AssetSequenceConnector
    | AssetFileConnector
    | AssetEventConnector
    | AssetRelationshipConnector
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
    | BaseTransformerStandardised
    | LookupRelationshipSourceTarget
    | SetType
)
