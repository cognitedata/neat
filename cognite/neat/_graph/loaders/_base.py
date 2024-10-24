from abc import ABC, abstractmethod
from collections.abc import Hashable, Iterable
from pathlib import Path
from typing import ClassVar, Generic, TypeVar

from cognite.client import CogniteClient
from cognite.client.data_classes.capabilities import Capability

from cognite.neat._issues import IssueList, NeatIssue, NeatIssueList
from cognite.neat._issues.errors import AuthorizationError
from cognite.neat._store import NeatGraphStore
from cognite.neat._utils.auxiliary import class_html_doc
from cognite.neat._utils.upload import UploadResult, UploadResultList

T_Output = TypeVar("T_Output")


# Sentinel value to indicate in the load method that all instances of a class have been loaded.
# https://en.wikipedia.org/wiki/Sentinel_value
class _END_OF_CLASS: ...


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
        return (item for item in self._load(stop_on_exception) if item is not _END_OF_CLASS)  # type: ignore[misc]

    @abstractmethod
    def _load(self, stop_on_exception: bool = False) -> Iterable[T_Output | NeatIssue | type[_END_OF_CLASS]]:
        """Load the graph with data."""
        pass

    @classmethod
    def _repr_html_(cls) -> str:
        return class_html_doc(cls)


class CDFLoader(BaseLoader[T_Output]):
    _UPLOAD_BATCH_SIZE: ClassVar[int] = 1000

    def load_into_cdf(
        self, client: CogniteClient, dry_run: bool = False, check_client: bool = True
    ) -> UploadResultList:
        return UploadResultList(self.load_into_cdf_iterable(client, dry_run, check_client))

    def load_into_cdf_iterable(
        self, client: CogniteClient, dry_run: bool = False, check_client: bool = True
    ) -> Iterable[UploadResult]:
        if check_client:
            missing_capabilities = client.iam.verify_capabilities(self._get_required_capabilities())
            if missing_capabilities:
                upload_result = UploadResult[Hashable](name=type(self).__name__)
                upload_result.issues.append(
                    AuthorizationError(action="Upload to CDF", reason=str(missing_capabilities))
                )
                yield upload_result
                return

        issues = IssueList()
        items: list[T_Output] = []
        for result in self._load(stop_on_exception=False):
            if isinstance(result, NeatIssue):
                issues.append(result)
            elif result is _END_OF_CLASS:
                ...
            else:
                # MyPy does not understand else means the item will be of type T_Output
                items.append(result)  # type: ignore[arg-type]

            if len(items) >= self._UPLOAD_BATCH_SIZE or result is _END_OF_CLASS:
                yield from self._upload_to_cdf(client, items, dry_run, issues)
                issues = IssueList()
                items = []
        if items:
            yield from self._upload_to_cdf(client, items, dry_run, issues)

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
    ) -> Iterable[UploadResult]:
        raise NotImplementedError
