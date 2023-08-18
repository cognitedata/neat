from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Relationship, RelationshipUpdate
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.rules.models import TransformationRules
from cognite.neat.workflows.steps.step_model import DataContract


class RulesData(DataContract):
    rules: TransformationRules

    @property
    def dataset_id(self) -> int:
        return self.rules.metadata.data_set_id


class PathData(DataContract):
    excel_file_path: Path


class SourceGraph(DataContract):
    graph: NeatGraphStore


class SolutionGraph(DataContract):
    graph: NeatGraphStore


class ClientData(DataContract):
    client: CogniteClient


class CategorizedAssets(DataContract):
    assets: tuple[dict, dict] | dict


class CategorizedRelationships(DataContract):
    relationships: (
        tuple[dict[str, list[Relationship | RelationshipUpdate]], dict[str, set]]
        | dict[str, list[Relationship | RelationshipUpdate]]
    )
