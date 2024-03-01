from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Asset, AssetUpdate, Relationship, RelationshipUpdate
from cognite.client.data_classes.data_modeling import EdgeApply, NodeApply

from cognite.neat.graph.stores import NeatGraphStoreBase
from cognite.neat.rules.exporter._rules2dms import DMSSchemaComponents
from cognite.neat.rules.models._rules import DMSRules, DomainRules, InformationRules
from cognite.neat.rules.models.rules import Rules
from cognite.neat.workflows.steps.step_model import DataContract


class RulesData(DataContract):
    """
    This represents the TransformationRules object.

    Args:
        rules: The TransformationRules object.
    """

    rules: Rules


class MultiRuleData(DataContract):
    domain: DomainRules | None = None
    information: InformationRules | None = None
    dms: DMSRules | None = None

    @classmethod
    def from_rules(cls, rules: DomainRules | InformationRules | DMSRules):
        if isinstance(rules, DomainRules):
            return cls(domain=rules)
        elif isinstance(rules, InformationRules):
            return cls(information=rules)
        elif isinstance(rules, DMSRules):
            return cls(dms=rules)
        else:
            raise ValueError(f"Unsupported rules type {type(rules)}")


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


class DMSSchemaComponentsData(DataContract):
    """
    This represents DMS Schema Model.

    Args:
        components: DMS Schema Components model.
    """

    components: DMSSchemaComponents
