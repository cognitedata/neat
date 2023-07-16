from pathlib import Path

from cognite.client import CogniteClient

from cognite.neat.core.loader import NeatGraphStore
from cognite.neat.core.rules.models import TransformationRules
from cognite.neat.core.workflow2.base import Data


class RulesData(Data):
    rules: TransformationRules

    @property
    def dataset_id(self) -> int:
        return self.rules.metadata.data_set_id


class PathData(Data):
    excel_file_path: Path


class SourceGraphData(Data):
    graph: NeatGraphStore


class SolutionGraphData(Data):
    graph: NeatGraphStore


class ClientData(Data):
    client: CogniteClient
