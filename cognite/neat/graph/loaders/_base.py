from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import Generic, Literal, TypeVar, overload

from cognite.client import CogniteClient
from cognite.client.data_classes.capabilities import Capability

from cognite.neat.graph import NeatGraphStoreBase
from cognite.neat.graph.issues.loader import FailedAuthorizationError
from cognite.neat.issues import NeatIssue
from cognite.neat.utils.upload import UploadDiffsID, UploadResultIDs

T_Output = TypeVar("T_Output")


class BaseLoader(ABC, Generic[T_Output]):
    _new_line = "\n"
    _encoding = "utf-8"

    def __init__(self, graph_store: NeatGraphStoreBase):
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


class CDFLoader(BaseLoader[T_Output]):
    @overload
    def load_into_cdf_iterable(
        self, client: CogniteClient, return_diffs: Literal[False] = False, dry_run: bool = False
    ) -> Iterable[UploadResultIDs]: ...

    @overload
    def load_into_cdf_iterable(
        self, client: CogniteClient, return_diffs: Literal[True], dry_run: bool = False
    ) -> Iterable[UploadDiffsID]: ...

    def load_into_cdf_iterable(
        self, client: CogniteClient, return_diffs: bool = False, dry_run: bool = False
    ) -> Iterable[UploadResultIDs] | Iterable[UploadDiffsID]:
        yield from self._load_into_cdf_iterable(client, return_diffs, dry_run)

    @overload
    def load_into_cdf(
        self, client: CogniteClient, return_diffs: Literal[False] = False, dry_run: bool = False
    ) -> list[UploadResultIDs]: ...

    @overload
    def load_into_cdf(
        self, client: CogniteClient, return_diffs: Literal[True], dry_run: bool = False
    ) -> list[UploadDiffsID]: ...

    def load_into_cdf(
        self, client: CogniteClient, return_diffs: bool = False, dry_run: bool = False
    ) -> list[UploadResultIDs] | list[UploadDiffsID]:
        return list(self._load_into_cdf_iterable(client, return_diffs, dry_run))  # type: ignore[return-value]

    def _load_into_cdf_iterable(
        self, client: CogniteClient, return_diffs: bool = False, dry_run: bool = False
    ) -> Iterable[UploadResultIDs] | Iterable[UploadDiffsID]:
        missing_capabilities = client.iam.verify_capabilities(self._get_required_capabilities())
        result_cls = UploadDiffsID if return_diffs else UploadResultIDs
        if missing_capabilities:
            error = FailedAuthorizationError(action="Upload to CDF", reason=str(missing_capabilities))
            result = result_cls(name=type(self).__name__)
            result.issues.append(error)
            yield result
            return

    @abstractmethod
    def _get_required_capabilities(self) -> list[Capability]:
        raise NotImplementedError
