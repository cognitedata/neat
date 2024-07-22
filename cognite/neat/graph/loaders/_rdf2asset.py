import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import cast

import yaml
from cognite.client import CogniteClient
from cognite.client.data_classes import AssetWrite
from cognite.client.data_classes.capabilities import AssetsAcl, Capability
from cognite.client.exceptions import CogniteAPIError

from cognite.neat.graph._tracking.base import Tracker
from cognite.neat.graph._tracking.log import LogTracker
from cognite.neat.graph.issues import loader as loader_issues
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.issues import NeatIssue, NeatIssueList
from cognite.neat.rules.analysis._asset import AssetAnalysis
from cognite.neat.rules.models import AssetRules
from cognite.neat.utils.upload import UploadResult

from ._base import _END_OF_CLASS, CDFLoader


@dataclass(frozen=True)
class AssetLoaderMetadataKeys:
    """Class holding mapping between NEAT metadata key names and their desired names
    in CDF Asset metadata

    Args:
        start_time: Start time key name
        end_time: End time key name
        update_time: Update time key name
        resurrection_time: Resurrection time key name
        identifier: Identifier key name
        active: Active key name
        type: Type key name
    """

    start_time: str = "start_time"
    end_time: str = "end_time"
    update_time: str = "update_time"
    resurrection_time: str = "resurrection_time"
    identifier: str = "identifier"
    active: str = "active"
    type: str = "type"

    def as_aliases(self) -> dict[str, str]:
        return {str(field.default): getattr(self, field.name) for field in fields(self)}


class AssetLoader(CDFLoader[AssetWrite]):
    """Load Assets from NeatGraph to Cognite Data Fusions.

    Args:
        graph_store (NeatGraphStore): The graph store to load the data into.
        rules (AssetRules): The rules to load the assets with.
        data_set_id (int): The CDF data set id to load the Assets into.
        use_orphanage (bool): Whether to use an orphanage for assets that are not part
                              of the hierarchy. Defaults to False.
        use_labels (bool): Whether to use labels for assets. Defaults to False.
        asset_external_id_prefix (str | None): The prefix to use for the external id of the assets.
                                               Defaults to None.
        metadata_keys (AssetLoaderMetadataKeys | None): Mapping between NEAT metadata key names and
                                                        their desired names in CDF Asset metadata. Defaults to None.
        create_issues (Sequence[NeatIssue] | None): A list of issues that occurred during reading. Defaults to None.
        tracker (type[Tracker] | None): The tracker to use. Defaults to None.
    """

    def __init__(
        self,
        graph_store: NeatGraphStore,
        rules: AssetRules,
        data_set_id: int,
        use_orphanage: bool = False,
        use_labels: bool = False,
        asset_external_id_prefix: str | None = None,
        metadata_keys: AssetLoaderMetadataKeys | None = None,
        create_issues: Sequence[NeatIssue] | None = None,
        tracker: type[Tracker] | None = None,
    ):
        super().__init__(graph_store)

        self.rules = rules
        self.data_set_id = data_set_id
        self.use_labels = use_labels

        self.orphanage = (
            AssetWrite.load(
                {
                    "dataSetId": self.data_set_id,
                    "externalId": (
                        f"{asset_external_id_prefix or ''}orphanage-{data_set_id}" if use_orphanage else None
                    ),
                    "name": "Orphanage",
                    "description": "Orphanage for assets whose parents do not exist",
                }
            )
            if use_orphanage
            else None
        )

        self.asset_external_id_prefix = asset_external_id_prefix
        self.metadata_keys = metadata_keys or AssetLoaderMetadataKeys()

        self.processed_assets: set[str] = set()
        self._issues = NeatIssueList[NeatIssue](create_issues or [])
        self._tracker: type[Tracker] = tracker or LogTracker

    def _load(self, stop_on_exception: bool = False) -> Iterable[AssetWrite | NeatIssue | type[_END_OF_CLASS]]:
        if self._issues.has_errors and stop_on_exception:
            raise self._issues.as_exception()
        elif self._issues.has_errors:
            yield from self._issues
            return
        if not self.rules:
            # There should already be an error in this case.
            return

        ordered_classes = AssetAnalysis(self.rules).class_topological_sort()

        tracker = self._tracker(
            type(self).__name__,
            [repr(class_.id) for class_ in ordered_classes],
            "classes",
        )

        if self.orphanage:
            yield self.orphanage
            self.processed_assets.add(cast(str, self.orphanage.external_id))

        for class_ in ordered_classes:
            tracker.start(repr(class_.id))

            property_renaming_config = AssetAnalysis(self.rules).define_asset_property_renaming_config(class_)

            for identifier, properties in self.graph_store.read(class_.suffix):
                fields = _process_properties(properties, property_renaming_config)
                # set data set id and external id
                fields["dataSetId"] = self.data_set_id
                fields["externalId"] = identifier

                # check on parent
                if "parentExternalId" in fields and fields["parentExternalId"] not in self.processed_assets:
                    error = loader_issues.InvalidInstanceError(
                        type_="asset",
                        identifier=identifier,
                        reason=(
                            f"Parent asset {fields['parentExternalId']} does not exist or failed creation"
                            f""" {
                                f', moving the asset {identifier} under orphanage {self.orphanage.external_id}'
                                if self.orphanage
                                else ''}"""
                        ),
                    )
                    tracker.issue(error)
                    if stop_on_exception:
                        raise error.as_exception()
                    yield error

                    # if orphanage is set asset will use orphanage as parent
                    if self.orphanage:
                        fields["parentExternalId"] = self.orphanage.external_id

                    # otherwise asset will be skipped
                    else:
                        continue

                try:
                    yield AssetWrite.load(fields)
                    self.processed_assets.add(identifier)
                except KeyError as e:
                    error = loader_issues.InvalidInstanceError(type_="asset", identifier=identifier, reason=str(e))
                    tracker.issue(error)
                    if stop_on_exception:
                        raise error.as_exception() from e
                    yield error

            yield _END_OF_CLASS

    def _get_required_capabilities(self) -> list[Capability]:
        return [
            AssetsAcl(
                actions=[
                    AssetsAcl.Action.Write,
                    AssetsAcl.Action.Read,
                ],
                scope=AssetsAcl.Scope.DataSet([self.data_set_id]),
            )
        ]

    def _upload_to_cdf(
        self,
        client: CogniteClient,
        items: list[AssetWrite],
        dry_run: bool,
        read_issues: NeatIssueList,
    ) -> Iterable[UploadResult]:
        try:
            upserted = client.assets.upsert(items, mode="replace")
        except CogniteAPIError as e:
            result = UploadResult[str](name="Asset", issues=read_issues)
            result.error_messages.append(str(e))
            result.failed_upserted.update(item.as_id() for item in e.failed + e.unknown)
            result.upserted.update(item.as_id() for item in e.successful)
            yield result
        else:
            for asset in upserted:
                result = UploadResult[str](name="asset", issues=read_issues)
                result.upserted.add(cast(str, asset.external_id))
                yield result

    def write_to_file(self, filepath: Path) -> None:
        if filepath.suffix not in [".json", ".yaml", ".yml"]:
            raise ValueError(f"File format {filepath.suffix} is not supported")
        dumped: dict[str, list] = {"assets": []}
        for item in self.load(stop_on_exception=False):
            key = {
                AssetWrite: "assets",
                NeatIssue: "issues",
                _END_OF_CLASS: "end_of_class",
            }.get(type(item))
            if key is None:
                # This should never happen, and is a bug in neat
                raise ValueError(f"Item {item} is not supported. This is a bug in neat please report it.")
            if key == "end_of_class":
                continue
            dumped[key].append(item.dump())
        with filepath.open("w", encoding=self._encoding, newline=self._new_line) as f:
            if filepath.suffix == ".json":
                json.dump(dumped, f, indent=2)
            else:
                yaml.safe_dump(dumped, f, sort_keys=False)


def _process_properties(properties: dict[str, list[str]], property_renaming_config: dict[str, str]) -> dict:
    metadata: dict[str, str] = {}
    fields: dict[str, str | dict] = {}

    for original_property, values in properties.items():
        if renamed_property := property_renaming_config.get(original_property, None):
            if renamed_property.startswith("metadata."):
                # Asset metadata contains only string values
                metadata[original_property] = ", ".join(values)
            else:
                # Asset fields can contain only one value
                fields[renamed_property] = values[0]

    if metadata:
        fields["metadata"] = metadata

    return fields
