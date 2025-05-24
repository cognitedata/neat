from ._base import BaseTransformerStandardised
from ._best_class_match import BestClassMatch
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
from ._object_mapper import ObjectMapper
from ._prune_graph import (
    AttachPropertyFromTargetToSource,
    PruneDanglingNodes,
    PruneDeadEndEdges,
    PruneInstancesOfUnknownType,
    PruneTypes,
)
from ._rdfpath import MakeConnectionOnExactMatch
from ._set_type_by_id import SetRDFTypeById
from ._value_type import ConnectionToLiteral, ConvertLiteral, LiteralToEntity, SetType, SplitMultiValueProperty

__all__ = [
    "AddAssetDepth",
    "AssetEventConnector",
    "AssetFileConnector",
    "AssetRelationshipConnector",
    "AssetSequenceConnector",
    "AssetTimeSeriesConnector",
    "AttachPropertyFromTargetToSource",
    "BestClassMatch",
    "ConnectionToLiteral",
    "ConvertLiteral",
    "LiteralToEntity",
    "LookupRelationshipSourceTarget",
    "MakeConnectionOnExactMatch",
    "ObjectMapper",
    "PruneDanglingNodes",
    "PruneDeadEndEdges",
    "PruneInstancesOfUnknownType",
    "PruneTypes",
    "RelationshipAsEdgeTransformer",
    "SetRDFTypeById",
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
    | BestClassMatch
)
