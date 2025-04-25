from collections.abc import Iterable
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.capabilities import Capability

from cognite.neat._issues import IssueList, NeatIssue
from cognite.neat._store import NeatGraphStore
from cognite.neat._utils.upload import UploadResult

from ._base import _END_OF_CLASS, _START_OF_CLASS, CDFLoader


class InstanceSpaceLoader(CDFLoader[dm.SpaceApply]):
    """Loads Instance Space into Cognite Data Fusion (CDF).

    This class also exposes the `space_by_instance_uri` method used by
    the DMSLoader to lookup space for each instance URI.

    Args:
        graph_store (NeatGraphStore): The graph store to load the data from.
        instance_space (str): The instance space to load the data into.

    """

    def __init__(
        self,
        graph_store: NeatGraphStore | None = None,
        instance_space: str | None = None,
        space_property: str | None = None,
        use_source_space: bool = False,
    ) -> None:
        self.graph_store = graph_store
        self.instance_space = instance_space
        self.space_property = space_property
        self.use_source_space = use_source_space

        self._has_looked_up = False

    def _get_required_capabilities(self) -> list[Capability]:
        raise NotImplementedError()

    def _upload_to_cdf(
        self,
        client: CogniteClient,
        items: list[dm.SpaceApply],
        dry_run: bool,
        read_issues: IssueList,
        class_name: str | None = None,
    ) -> Iterable[UploadResult]:
        raise NotImplementedError()

    def write_to_file(self, filepath: Path) -> None:
        raise NotImplementedError()

    def _load(
        self, stop_on_exception: bool = False
    ) -> Iterable[dm.SpaceApply | NeatIssue | type[_END_OF_CLASS] | _START_OF_CLASS]:
        raise NotImplementedError()
