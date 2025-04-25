import json
from collections.abc import Iterable
from pathlib import Path

import yaml
from cognite.client import data_modeling as dm
from cognite.client.data_classes.capabilities import Capability, DataModelsAcl

from cognite.neat._client import NeatClient
from cognite.neat._client._api.data_modeling_loaders import MultiCogniteAPIError
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
        return [
            DataModelsAcl(
                actions=[
                    DataModelsAcl.Action.Write,
                    DataModelsAcl.Action.Read,
                ],
                scope=DataModelsAcl.Scope.All(),
            )
        ]

    def _upload_to_cdf(
        self,
        client: NeatClient,
        items: list[dm.SpaceApply],
        dry_run: bool,
        read_issues: IssueList,
        class_name: str | None = None,
    ) -> Iterable[UploadResult]:
        cdf_items = client.data_modeling.spaces.retrieve([item.space for item in items])
        cdf_idem_by_id = {item.space: item for item in cdf_items}

        to_create = dm.SpaceApplyList([])
        to_update = dm.SpaceApplyList([])
        unchanged = dm.SpaceApplyList([])

        for local_space in items:
            cdf_space = cdf_idem_by_id.get(local_space.space)
            if cdf_space is None:
                to_create.append(local_space)
            elif cdf_space != local_space.as_write():
                to_update.append(local_space)
            else:
                unchanged.append(local_space)
        loader = client.loaders.spaces
        results: UploadResult[str] = UploadResult(class_name or loader.resource_name)
        results.unchanged.update(unchanged.as_ids())
        if dry_run:
            results.created.update(to_create.as_ids())
            results.changed.update(to_update.as_ids())
            yield results
        if to_create:
            try:
                client.loaders.spaces.create(to_create)
            except MultiCogniteAPIError as e:
                results.failed_created.update(to_create.as_ids())
                for error in e.errors:
                    results.error_messages.append(f"Failed to create {loader.resource_name}: {error!s}")
            else:
                results.created.update(to_create.as_ids())

        if to_update:
            try:
                client.loaders.spaces.update(to_update)
            except MultiCogniteAPIError as e:
                results.failed_changed.update(to_update.as_ids())
                for error in e.errors:
                    results.error_messages.append(f"Failed to update {loader.resource_name}: {error!s}")
            else:
                results.changed.update(to_update.as_ids())

        yield results

    def write_to_file(self, filepath: Path) -> None:
        """Dumps the instance spaces to file."""
        if filepath.suffix not in [".json", ".yaml", ".yml"]:
            raise ValueError(f"File format {filepath.suffix} is not supported")
        dumped: dict[str, list] = {"spaces": [], "issues": []}
        for item in self.load(stop_on_exception=False):
            key = {
                dm.SpaceApply: "spaces",
                NeatIssue: "issues",
            }.get(type(item))
            if key is None:
                # This should never happen, and is a bug in neat
                raise ValueError(f"Item {item} is not supported. This is a bug in neat please report it.")
            dumped[key].append(item.dump())
        with filepath.open("w", encoding=self._encoding, newline=self._new_line) as f:
            if filepath.suffix == ".json":
                json.dump(dumped, f, indent=2)
            else:
                yaml.safe_dump(dumped, f, sort_keys=False)

    def _load(
        self, stop_on_exception: bool = False
    ) -> Iterable[dm.SpaceApply | NeatIssue | type[_END_OF_CLASS] | _START_OF_CLASS]:
        # Case 1: Same instance space for all instances:
        if self.instance_space is not None and self.space_property is None:
            yield dm.SpaceApply(space=self.instance_space)
            return
        raise NotImplementedError()
