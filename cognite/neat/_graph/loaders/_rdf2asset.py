import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, cast

import yaml
from cognite.client import CogniteClient
from cognite.client.data_classes import (
    AssetWrite,
    LabelDefinitionWrite,
    RelationshipWrite,
)
from cognite.client.data_classes.capabilities import (
    AssetsAcl,
    Capability,
    RelationshipsAcl,
)
from cognite.client.exceptions import CogniteAPIError, CogniteDuplicatedError

from cognite.neat._graph._tracking.base import Tracker
from cognite.neat._graph._tracking.log import LogTracker
from cognite.neat._issues import IssueList, NeatError, NeatIssue, NeatIssueList
from cognite.neat._issues.errors import ResourceCreationError, ResourceNotFoundError
from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.analysis._asset import AssetAnalysis
from cognite.neat._rules.models import AssetRules
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._store import NeatGraphStore
from cognite.neat._utils.auxiliary import create_sha256_hash
from cognite.neat._utils.upload import UploadResult

from ._base import _END_OF_CLASS, CDFLoader


class AssetLoader(CDFLoader[AssetWrite]):
    """Load Assets and their relationships from NeatGraph to Cognite Data Fusions.

    Args:
        graph_store (NeatGraphStore): The graph store to load the data into.
        rules (AssetRules): The rules to load the assets with.
        data_set_id (int): The CDF data set id to load the Assets into.
        use_orphanage (bool): Whether to use an orphanage for assets that are not part
                              of the hierarchy. Defaults to False.
        use_labels (bool): Whether to use labels for assets. Defaults to False.
        external_id_prefix (str | None): The prefix to use for the external ids. Defaults to None.
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
        external_id_prefix: str | None = None,
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
                    "externalId": (f"{external_id_prefix or ''}orphanage-{data_set_id}" if use_orphanage else None),
                    "name": "Orphanage",
                    "description": "Orphanage for assets whose parents do not exist",
                }
            )
            if use_orphanage
            else None
        )

        self.external_id_prefix = external_id_prefix

        self.processed_assets: set[str] = set()
        self._issues = IssueList(create_issues or [])
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

        if self.use_labels:
            yield from self._create_labels()

        if self.orphanage:
            yield self.orphanage
            self.processed_assets.add(cast(str, self.orphanage.external_id))

        yield from self._create_assets(ordered_classes, tracker, stop_on_exception)
        yield from self._create_relationship(ordered_classes, tracker, stop_on_exception)

    def _create_labels(self) -> Iterable[Any]:
        for label in AssetAnalysis(self.rules).define_labels():
            yield LabelDefinitionWrite(name=label, external_id=label, data_set_id=self.data_set_id)
        yield _END_OF_CLASS

    def _create_assets(
        self,
        ordered_classes: list[ClassEntity],
        tracker: Tracker,
        stop_on_exception: bool,
    ) -> Iterable[Any]:
        error: NeatError
        for class_ in ordered_classes:
            tracker.start(repr(class_.id))

            property_renaming_config = AssetAnalysis(self.rules).define_asset_property_renaming_config(class_)

            for identifier, properties in self.graph_store.read(class_.suffix):
                identifier = f"{self.external_id_prefix or ''}{identifier}"

                fields = _process_asset_properties(properties, property_renaming_config)
                # set data set id and external id
                fields["dataSetId"] = self.data_set_id
                fields["externalId"] = identifier

                if self.use_labels:
                    fields["labels"] = [class_.suffix]

                if parent_external_id := fields.get("parentExternalId", None):
                    fields["parentExternalId"] = f"{self.external_id_prefix or ''}{parent_external_id}"

                # check on parent
                if "parentExternalId" in fields and fields["parentExternalId"] not in self.processed_assets:
                    error = ResourceNotFoundError(
                        fields["parentExternalId"],
                        EntityTypes.asset,
                        identifier,
                        EntityTypes.asset,
                        f"Moving the asset {identifier} under orphanage {self.orphanage.external_id}"
                        if self.orphanage
                        else "",
                    )
                    tracker.issue(error)
                    if stop_on_exception:
                        raise error
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
                    error = ResourceCreationError(identifier, EntityTypes.asset, error=str(e))
                    tracker.issue(error)
                    if stop_on_exception:
                        raise error from e
                    yield error

            yield _END_OF_CLASS

    def _create_relationship(
        self,
        ordered_classes: list[ClassEntity],
        tracker: Tracker,
        stop_on_exception: bool,
    ) -> Iterable[Any]:
        for class_ in ordered_classes:
            tracker.start(repr(class_.id))

            property_renaming_config = AssetAnalysis(self.rules).define_relationship_property_renaming_config(class_)

            # class does not have any relationship properties
            if not property_renaming_config:
                continue

            for source_external_id, properties in self.graph_store.read(class_.suffix):
                relationships = _process_relationship_properties(properties, property_renaming_config)

                source_external_id = f"{self.external_id_prefix or ''}{source_external_id}"

                # check if source asset exists
                if source_external_id not in self.processed_assets:
                    error = ResourceCreationError(
                        resource_type=EntityTypes.relationship,
                        identifier=source_external_id,
                        error=(
                            f"Asset {source_external_id} does not exist! "
                            "Aborting creation of relationships which use this asset as the source."
                        ),
                    )
                    tracker.issue(error)
                    if stop_on_exception:
                        raise error
                    yield error
                    continue

                for label, target_external_ids in relationships.items():
                    # we can have 1-many relationships
                    for target_external_id in target_external_ids:
                        target_external_id = f"{self.external_id_prefix or ''}{target_external_id}"
                        # check if source asset exists
                        if target_external_id not in self.processed_assets:
                            error = ResourceCreationError(
                                resource_type=EntityTypes.relationship,
                                identifier=target_external_id,
                                error=(
                                    f"Asset {target_external_id} does not exist! "
                                    f"Cannot create relationship between {source_external_id}"
                                    f" and {target_external_id}. "
                                ),
                            )
                            tracker.issue(error)
                            if stop_on_exception:
                                raise error
                            yield error
                            continue

                        external_id = "relationship_" + create_sha256_hash(f"{source_external_id}_{target_external_id}")
                        try:
                            yield RelationshipWrite(
                                external_id=external_id,
                                source_external_id=source_external_id,
                                target_external_id=target_external_id,
                                source_type="asset",
                                target_type="asset",
                                data_set_id=self.data_set_id,
                                labels=[label] if self.use_labels else None,
                            )
                        except KeyError as e:
                            error = ResourceCreationError(
                                resource_type=EntityTypes.relationship,
                                identifier=external_id,
                                error=str(e),
                            )
                            tracker.issue(error)
                            if stop_on_exception:
                                raise error from e
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
            ),
            RelationshipsAcl(
                actions=[
                    RelationshipsAcl.Action.Write,
                    RelationshipsAcl.Action.Read,
                ],
                scope=RelationshipsAcl.Scope.DataSet([self.data_set_id]),
            ),
        ]

    def _upload_to_cdf(
        self,
        client: CogniteClient,
        items: list[AssetWrite] | list[RelationshipWrite] | list[LabelDefinitionWrite],
        dry_run: bool,
        read_issues: NeatIssueList,
    ) -> Iterable[UploadResult]:
        if isinstance(items[0], AssetWrite) and all(isinstance(item, AssetWrite) for item in items):
            yield from self._upload_assets_to_cdf(client, cast(list[AssetWrite], items), dry_run, read_issues)
        elif isinstance(items[0], RelationshipWrite) and all(isinstance(item, RelationshipWrite) for item in items):
            yield from self._upload_relationships_to_cdf(
                client, cast(list[RelationshipWrite], items), dry_run, read_issues
            )
        elif isinstance(items[0], LabelDefinitionWrite) and all(
            isinstance(item, LabelDefinitionWrite) for item in items
        ):
            yield from self._upload_labels_to_cdf(client, cast(list[LabelDefinitionWrite], items), dry_run, read_issues)
        else:
            raise ValueError(f"Item {items[0]} is not supported. This is a bug in neat please report it.")

    def _upload_labels_to_cdf(
        self,
        client: CogniteClient,
        items: list[LabelDefinitionWrite],
        dry_run: bool,
        read_issues: NeatIssueList,
    ) -> Iterable[UploadResult]:
        try:
            created = client.labels.create(items)
        except (CogniteAPIError, CogniteDuplicatedError) as e:
            result = UploadResult[str](name="Label", issues=read_issues)
            result.error_messages.append(str(e))
            result.failed_created.update(item.external_id for item in e.failed + e.unknown)
            result.created.update(item.external_id for item in e.successful)
            yield result
        else:
            for label in created:
                result = UploadResult[str](name="Label", issues=read_issues)
                result.upserted.add(cast(str, label.external_id))
                yield result

    def _upload_assets_to_cdf(
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
            result.failed_upserted.update(item.external_id for item in e.failed + e.unknown)
            result.upserted.update(item.external_id for item in e.successful)
            yield result
        else:
            for asset in upserted:
                result = UploadResult[str](name="Asset", issues=read_issues)
                result.upserted.add(cast(str, asset.external_id))
                yield result

    def _upload_relationships_to_cdf(
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
            result.failed_upserted.update(item.external_id for item in e.failed + e.unknown)
            result.upserted.update(item.external_id for item in e.successful)
            yield result
        else:
            for relationship in upserted:
                result = UploadResult[str](name="relationship", issues=read_issues)
                result.upserted.add(cast(str, relationship.external_id))
                yield result

    def write_to_file(self, filepath: Path) -> None:
        if filepath.suffix not in [".json", ".yaml", ".yml"]:
            raise ValueError(f"File format {filepath.suffix} is not supported")
        dumped: dict[str, list] = {"assets": [], "relationship": []}
        for item in self.load(stop_on_exception=False):
            key = {
                AssetWrite: "assets",
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


def _process_asset_properties(properties: dict[str, list[str]], property_renaming_config: dict[str, str]) -> dict:
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


def _process_relationship_properties(
    properties: dict[str, list[str]], property_renaming_config: dict[str, str]
) -> dict:
    relationships: dict[str, list[str]] = {}

    for original_property, values in properties.items():
        if renamed_property := property_renaming_config.get(original_property, None):
            relationships[renamed_property] = values

    return relationships
