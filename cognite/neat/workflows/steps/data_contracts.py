from pathlib import Path

from cognite.client import CogniteClient

from cognite.neat.graph.extractors import NeatGraphStore
from cognite.neat.rules.models import TransformationRules
from cognite.neat.workflows.workflow.step_model import DataContract


class RulesData(DataContract):
    rules: TransformationRules

    @property
    def dataset_id(self) -> int:
        return self.rules.metadata.data_set_id


class PathData(DataContract):
    excel_file_path: Path


class SourceGraphData(DataContract):
    graph: NeatGraphStore


class SolutionGraphData(DataContract):
    graph: NeatGraphStore


class ClientData(DataContract):
    client: CogniteClient
