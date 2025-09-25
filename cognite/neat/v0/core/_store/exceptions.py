"""These are special exceptions that are used by the store to signal invalid transformers"""

from dataclasses import dataclass

from cognite.neat.v0.core._data_model.importers import BaseImporter
from cognite.neat.v0.core._data_model.transformers import VerifiedDataModelTransformer
from cognite.neat.v0.core._instances.extractors import KnowledgeGraphExtractor
from cognite.neat.v0.core._issues import IssueList

from ._provenance import Activity


class NeatStoreError(Exception):
    """Base class for all exceptions in the store module"""

    def __str__(self) -> str:
        return type(self).__name__


class ActivityFailed(NeatStoreError):
    """Raised when an activity fails"""

    def __init__(
        self,
        activity: Activity,
        issue_list: IssueList,
        tool: BaseImporter | VerifiedDataModelTransformer | KnowledgeGraphExtractor,
    ) -> None:
        self.activity = activity
        self.issue_list = issue_list
        self.tool = tool

    def __str__(self) -> str:
        return self.tool.description


@dataclass
class InvalidActivityInput(NeatStoreError, RuntimeError):
    """Raised when an invalid activity is attempted"""

    expected: tuple[type, ...]
    have: tuple[type, ...]


class InvalidActivityOutput(NeatStoreError):
    """Raised when an activity has an invalid output"""

    def __init__(self, activity: Activity, output: str) -> None:
        self.activity = activity
        self.output = output

    def __str__(self) -> str:
        return f"{super().__str__()}: {self.activity.id_} -> {self.output}"


class EmptyStore(NeatStoreError, RuntimeError):
    """Raised when the store is empty"""

    ...
