import json
from collections.abc import Iterable
from pathlib import Path

import yaml
from cognite.client.data_classes.capabilities import Capability, LocationFiltersAcl
from cognite.client.data_classes.data_modeling import DataModelId
from cognite.client.exceptions import CogniteAPIError

from cognite.neat.core._client import NeatClient
from cognite.neat.core._client.data_classes.location_filters import LocationFilterWrite, LocationFilterWriteList
from cognite.neat.core._issues import IssueList, NeatIssue
from cognite.neat.core._utils.upload import UploadResult

from ._base import _END_OF_CLASS, _START_OF_CLASS, CDFLoader


class LocationFilterLoader(CDFLoader[LocationFilterWrite]):
    """Creates a location filter in CDF

    Args:
        name (str | None): Name of the location filter. If None, a default name will be generated.
        data_model_id (DataModelId | None): Data model ID for the location filter.
        instance_spaces (list[str] | None): List of instance spaces for the location filter.
    """

    def __init__(
        self,
        data_model_id: DataModelId,
        instance_spaces: list[str],
        name: str | None = None,
    ) -> None:
        self.data_model_id = data_model_id
        self.instance_spaces = instance_spaces
        self.name = name

    def _get_required_capabilities(self) -> list[Capability]:
        return [
            LocationFiltersAcl(
                actions=[LocationFiltersAcl.Action.Read, LocationFiltersAcl.Action.Write],
                scope=LocationFiltersAcl.Scope.All(),
            )
        ]

    def _upload_to_cdf(
        self,
        client: NeatClient,
        items: list[LocationFilterWrite],
        dry_run: bool,
        read_issues: IssueList,
        class_name: str | None = None,
    ) -> Iterable[UploadResult]:
        ids = {item.external_id for item in items if item.external_id}
        cdf_item_by_ids = {
            item.external_id: item
            for item in client.location_filters.list()
            if item.external_id and item.external_id in ids
        }

        to_create = LocationFilterWriteList([])
        to_update = LocationFilterWriteList([])
        unchanged = LocationFilterWriteList([])

        for local_filter in items:
            if local_filter.external_id is None:
                continue
            cdf_filter = cdf_item_by_ids.get(local_filter.external_id)
            if cdf_filter is None:
                to_create.append(local_filter)
            elif cdf_filter != local_filter.as_write():
                to_update.append(local_filter)
            else:
                unchanged.append(local_filter)

        results: UploadResult[str] = UploadResult("location filters")
        results.unchanged.update(unchanged.as_external_ids())
        if dry_run:
            results.created.update(to_create.as_external_ids())
            results.changed.update(to_update.as_external_ids())
            yield results
        if to_create:
            for create_item in to_create:
                if create_item.external_id is None:
                    continue
                try:
                    client.location_filters.create(create_item)
                except CogniteAPIError as e:
                    results.failed_created.add(create_item.external_id)
                    results.error_messages.append(f"Failed to create location filter: {e!s}")
                else:
                    results.created.add(create_item.external_id)

        if to_update:
            for update_item in to_update:
                try:
                    client.location_filters.create(update_item)
                except CogniteAPIError as e:
                    results.failed_changed.add(update_item.external_id)
                    results.error_messages.append(f"Failed to update location filter: {e!s}")
                else:
                    results.changed.add(update_item.external_id)

        yield results

    def write_to_file(self, filepath: Path) -> None:
        """Write the location filter to a file.

        Args:
            filepath (Path): Path to the file.
        """
        if filepath.suffix not in [".json", ".yaml", ".yml"]:
            raise ValueError(f"File format {filepath.suffix} is not supported")
        dumped: list[dict[str, object]] = []
        for item in self._load():
            if isinstance(item, LocationFilterWrite):
                dumped.append(item.dump())
        with filepath.open("w", encoding=self._encoding, newline=self._new_line) as f:
            if filepath.suffix == ".json":
                json.dump(dumped, f, indent=2)
            else:
                yaml.safe_dump(dumped, f, sort_keys=False)

    def _load(
        self, stop_on_exception: bool = False
    ) -> Iterable[LocationFilterWrite | NeatIssue | type[_END_OF_CLASS] | _START_OF_CLASS]:
        data_model_str = (
            f"{self.data_model_id.space}:{self.data_model_id.external_id}(version={self.data_model_id.version})"
        )
        name = self.name or f"Location Filter for {data_model_str}"
        yield LocationFilterWrite(
            external_id=name.replace(" ", "_").casefold(),
            name=name,
            description=f"Location filter for {data_model_str}",
            data_models=[self.data_model_id],
            instance_spaces=self.instance_spaces,
            data_modeling_type="DATA_MODELING_ONLY",
        )
