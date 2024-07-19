import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import cast

import yaml
from cognite.client import CogniteClient
from cognite.client.data_classes import RelationshipWrite
from cognite.client.data_classes.capabilities import Capability, RelationshipsAcl
from cognite.client.exceptions import CogniteAPIError

from cognite.neat.graph._tracking.base import Tracker
from cognite.neat.graph._tracking.log import LogTracker
from cognite.neat.graph.issues import loader as loader_issues
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.issues import NeatIssue, NeatIssueList
from cognite.neat.rules.analysis._asset import AssetAnalysis
from cognite.neat.rules.models import AssetRules
from cognite.neat.utils.auxiliary import create_sha256_hash
from cognite.neat.utils.upload import UploadResult

from ._base import _END_OF_CLASS, CDFLoader


class RelationshipLoader(CDFLoader[RelationshipWrite]):
    """Load Relationship from NeatGraph to Cognite Data Fusions.

    Args:
        graph_store (NeatGraphStore): The graph store to load the data into.
        rules (AssetRules): The rules to load the assets with.
        data_set_id (int): The CDF data set id to load the Assets into.
        use_labels (bool): Whether to use labels for assets. Defaults to False.
        relationship_external_id_prefix (str | None): The prefix to use for the external id of the assets.
                                                      Defaults to None.
        create_issues (Sequence[NeatIssue] | None): A list of issues that occurred during reading. Defaults to None.
        tracker (type[Tracker] | None): The tracker to use. Defaults to None.
    """

    def __init__(
        self,
        graph_store: NeatGraphStore,
        rules: AssetRules,
        data_set_id: int,
        use_labels: bool = False,
        relationship_external_id_prefix: str | None = None,
        processed_assets: set[str] | None = None,
        create_issues: Sequence[NeatIssue] | None = None,
        tracker: type[Tracker] | None = None,
    ):
        super().__init__(graph_store)
        self.rules = rules
        self.data_set_id = data_set_id
        self.use_labels = use_labels
        self.relationship_external_id_prefix = relationship_external_id_prefix
        self.processed_assets = processed_assets
        self._issues = NeatIssueList[NeatIssue](create_issues or [])
        self._tracker: type[Tracker] = tracker or LogTracker

    def _load(self, stop_on_exception: bool = False) -> Iterable[RelationshipWrite | NeatIssue | type[_END_OF_CLASS]]:
        if self._issues.has_errors and stop_on_exception:
            raise self._issues.as_exception()
        elif self._issues.has_errors:
            yield from self._issues
            return
        if not self.rules:
            # There should already be an error in this case.
            return

        # only classes that contain relationships definitions
        ordered_classes = AssetAnalysis(self.rules).relationship_definition().keys()

        tracker = self._tracker(
            type(self).__name__,
            [repr(class_.id) for class_ in ordered_classes],
            "classes",
        )

        for class_ in ordered_classes:
            tracker.start(repr(class_.id))

            property_renaming_config = AssetAnalysis(self.rules).define_relationship_property_renaming_config(class_)

            for source_external_id, properties in self.graph_store.read(class_.suffix):
                relationships = _process_properties(properties, property_renaming_config)

                for _, target_external_ids in relationships.items():
                    for target_external_id in target_external_ids:
                        external_id = create_sha256_hash(f"{source_external_id}_{target_external_id}")
                        try:
                            yield RelationshipWrite(
                                external_id=external_id,
                                source_external_id=source_external_id,
                                target_external_id=target_external_id,
                                source_type="asset",
                                target_type="asset",
                            )
                        except KeyError as e:
                            error = loader_issues.InvalidInstanceError(
                                type_="asset", identifier=external_id, reason=str(e)
                            )
                            tracker.issue(error)
                            if stop_on_exception:
                                raise error.as_exception() from e
                            yield error

            yield _END_OF_CLASS

    def _get_required_capabilities(self) -> list[Capability]:
        return [
            RelationshipsAcl(
                actions=[
                    RelationshipsAcl.Action.Write,
                    RelationshipsAcl.Action.Read,
                ],
                scope=RelationshipsAcl.Scope.DataSet([self.data_set_id]),
            )
        ]

    def _upload_to_cdf(
        self,
        client: CogniteClient,
        items: list[RelationshipWrite],
        dry_run: bool,
        read_issues: NeatIssueList,
    ) -> Iterable[UploadResult]:
        try:
            upserted = client.relationships.upsert(items, mode="replace")
        except CogniteAPIError as e:
            result = UploadResult[str](name="Relationship", issues=read_issues)
            result.error_messages.append(str(e))
            result.failed_upserted.update(item.as_id() for item in e.failed + e.unknown)
            result.created.update(item.as_id() for item in e.successful)
            yield result
        else:
            for asset in upserted:
                result = UploadResult[str](name="relationship", issues=read_issues)
                result.created.add(cast(str, asset.external_id))
                yield result

    def write_to_file(self, filepath: Path) -> None:
        if filepath.suffix not in [".json", ".yaml", ".yml"]:
            raise ValueError(f"File format {filepath.suffix} is not supported")
        dumped: dict[str, list] = {"relationship": []}
        for item in self.load(stop_on_exception=False):
            key = {
                RelationshipWrite: "relationship",
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
    relationships: dict[str, list[str]] = {}

    for original_property, values in properties.items():
        if renamed_property := property_renaming_config.get(original_property, None):
            relationships[renamed_property] = values

    return relationships
