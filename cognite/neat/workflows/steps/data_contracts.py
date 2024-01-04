from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Asset, AssetUpdate, Relationship, RelationshipUpdate
from cognite.client.data_classes.data_modeling import EdgeApply, NodeApply

from cognite.neat.graph.stores import NeatGraphStoreBase
from cognite.neat.rules.exporter._rules2dms import DataModel
from cognite.neat.rules.models.rules import Rules
from cognite.neat.workflows.steps.step_model import DataContract


class RulesData(DataContract):
    """
    This represents the TransformationRules object.

    Args:
        rules: The TransformationRules object.
    """

    rules: Rules


class PathData(DataContract):
    """
    This represents the path to the excel file.

    Args:
        excel_file_path: The path to the excel file.
    """

    excel_file_path: Path


class SourceGraph(DataContract):
    """
    This represents the source graph.

    Args:
        graph: The source graph.
    """

    graph: NeatGraphStoreBase


class SolutionGraph(DataContract):
    """
    This represents the solution graph.

    Args:
        graph (NeatGraphStoreBase): The solution graph.

    """

    graph: NeatGraphStoreBase


class ClientData(DataContract):
    """
    This represents an instantiated CogniteClient object.

    Args:
        client: The CogniteClient object.
    """

    client: CogniteClient


class CategorizedAssets(DataContract):
    """ "
    This represents the categorized assets.

    Args:
        assets: The categorized assets.
    """

    assets: dict[str, list[Asset | AssetUpdate]]


class CategorizedRelationships(DataContract):
    """
    This represents the categorized relationships.

    Args:
        relationships: The categorized relationships.

    """

    relationships: dict[str, list[Relationship] | list[RelationshipUpdate]]


class Nodes(DataContract):
    """
    This represents nodes.

    Args:
        nodes: list of nodes.
    """

    nodes: list[NodeApply]


class Edges(DataContract):
    """
    This represents edges.

    Args:
        edges: list of edges.
    """

    edges: list[EdgeApply]


class DMSDataModel(DataContract):
    """
    This represents DMS Data Model.

    Args:
        data_model: DMS data model.
    """

    data_model: DataModel
