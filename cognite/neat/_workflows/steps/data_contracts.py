from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import (
    Asset,
    AssetUpdate,
    Relationship,
    RelationshipUpdate,
)
from cognite.client.data_classes.data_modeling import EdgeApply, NodeApply

from cognite.neat._rules.models import (
    AssetRules,
    DMSRules,
    DomainRules,
    InformationRules,
)
from cognite.neat._store import NeatGraphStore
from cognite.neat._workflows.steps.step_model import DataContract


class MultiRuleData(DataContract):
    domain: DomainRules | None = None
    information: InformationRules | None = None
    asset: AssetRules | None = None
    dms: DMSRules | None = None

    @classmethod
    def from_rules(cls, rules: DomainRules | InformationRules | AssetRules | DMSRules):
        if isinstance(rules, DomainRules):
            return cls(domain=rules)
        elif isinstance(rules, InformationRules):
            return cls(information=rules)
        elif isinstance(rules, AssetRules):
            return cls(asset=rules)
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


class NeatGraph(DataContract):
    """
    This represents the neat graph.

    Args:
        graph: The neat graph store.
    """

    graph: NeatGraphStore


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
