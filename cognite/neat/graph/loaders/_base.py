from abc import ABC, abstractmethod
from collections.abc import Hashable, Iterable
from pathlib import Path
from typing import ClassVar, Generic, TypeVar

from cognite.client import CogniteClient
from cognite.client.data_classes.capabilities import Capability

from cognite.neat.graph import NeatGraphStore
from cognite.neat.graph.issues.loader import FailedAuthorizationError
from cognite.neat.issues import NeatIssue, NeatIssueList
from cognite.neat.utils.auxiliary import class_html_doc
from cognite.neat.utils.upload import UploadResult, UploadResultList

T_Output = TypeVar("T_Output")


class BaseLoader(ABC, Generic[T_Output]):
    _new_line = "\n"
    _encoding = "utf-8"

    def __init__(self, graph_store: NeatGraphStore):
        self.graph_store = graph_store

    @abstractmethod
    def write_to_file(self, filepath: Path) -> None:
        raise NotImplementedError

    def load(self, stop_on_exception: bool = False) -> Iterable[T_Output | NeatIssue]:
        """Load the graph with data."""
        return self._load(stop_on_exception)

    @abstractmethod
    def _load(self, stop_on_exception: bool = False) -> Iterable[T_Output | NeatIssue]:
        """Load the graph with data."""
        pass

    @classmethod
    def _repr_html_(cls) -> str:
        return class_html_doc(cls)


class CDFLoader(BaseLoader[T_Output]):
    _UPLOAD_BATCH_SIZE: ClassVar[int] = 1000

    def load_into_cdf(self, client: CogniteClient, dry_run: bool = False) -> UploadResultList:
        return UploadResultList(self.load_into_cdf_iterable(client, dry_run))

    def load_into_cdf_iterable(self, client: CogniteClient, dry_run: bool = False) -> Iterable[UploadResult]:
        missing_capabilities = client.iam.verify_capabilities(self._get_required_capabilities())
        if missing_capabilities:
            upload_result = UploadResult[Hashable](name=type(self).__name__)
            upload_result.issues.append(
                FailedAuthorizationError(action="Upload to CDF", reason=str(missing_capabilities))
            )
            yield upload_result
            return

        issues = NeatIssueList[NeatIssue]()
        items: list[T_Output] = []
        for result in self.load(stop_on_exception=False):
            if isinstance(result, NeatIssue):
                issues.append(result)
            else:
                items.append(result)

            if len(items) >= self._UPLOAD_BATCH_SIZE:
                yield self._upload_to_cdf(client, items, dry_run, issues)
                issues = NeatIssueList[NeatIssue]()
                items = []
        if items:
            yield self._upload_to_cdf(client, items, dry_run, issues)

    @abstractmethod
    def _get_required_capabilities(self) -> list[Capability]:
        raise NotImplementedError

    @abstractmethod
    def _upload_to_cdf(
        self,
        client: CogniteClient,
        items: list[T_Output],
        dry_run: bool,
        read_issues: NeatIssueList,
    ) -> UploadResult:
        raise NotImplementedError
