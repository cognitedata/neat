from pathlib import Path
from typing import Union

from cognite.client import CogniteClient

from cognite.neat.stores.graph_store import NeatGraphStore
from cognite.neat.rules.models import TransformationRules
from cognite.neat.workflows.steps.step_model import DataContract
from cognite.client.data_classes import Relationship, RelationshipUpdate


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
    assets: Union[tuple[dict, dict], dict]


class CategorizedRelationships(DataContract):
    relationships: Union[
        tuple[dict[str, list[Union[Relationship, RelationshipUpdate]]], dict[str, set]],
        dict[str, list[Union[Relationship, RelationshipUpdate]]],
    ]
