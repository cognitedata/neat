from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import AssetWrite
from cognite.client.data_classes.capabilities import Capability

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
        self.use_orphanage = use_orphanage

        self.orphanage_external_id = (
            f"{asset_external_id_prefix or ''}orphanage-{data_set_id}" if use_orphanage else None
        )

        self.asset_external_id_prefix = asset_external_id_prefix
        self.metadata_keys = metadata_keys or AssetLoaderMetadataKeys()

        self._issues = NeatIssueList[NeatIssue](create_issues or [])
        self._tracker: type[Tracker] = tracker or LogTracker

    def _create_validation_classes(self) -> None:
        # need to get back class-property pairs where are definition of
        # asset implementations, extend InformationRulesAnalysis make it generic

        # by default if there is not explicitly stated external_id
        # use rdf:type and drop the prefix

        # based on those create pydantic model AssetDefinition
        # which will have .to_asset_write()

        raise NotImplementedError("Not implemented yet, this is placeholder")

    def categorize_assets(self, client: CogniteClient) -> None:
        """Categorize assets to those to be created, updated, decommissioned, or resurrected"""

        raise NotImplementedError("Not implemented yet, this is placeholder")

    def _load(self, stop_on_exception: bool = False) -> Iterable[AssetWrite | NeatIssue | type[_END_OF_CLASS]]:
        if self._issues.has_errors and stop_on_exception:
            raise self._issues.as_exception()
        elif self._issues.has_errors:
            yield from self._issues
            return
        if not self.rules:
            # There should already be an error in this case.
            return

        class_ids = [repr(class_.class_.id) for class_ in self.rules.classes]
        tracker = self._tracker(type(self).__name__, class_ids, "classes")

        for class_ in self.rules.classes:
            tracker.start(repr(class_.class_.id))

            property_renaming_config = AssetAnalysis(self.rules).define_property_renaming_config(class_.class_)

            for identifier, properties in self.graph_store.read(class_.class_.suffix):
                fields = _process_properties(properties, property_renaming_config)
                # set data set id and external id
                fields["data_set_id"] = self.data_set_id
                fields["external_id"] = identifier

                try:
                    yield AssetWrite.load(fields)
                except KeyError as e:
                    error = loader_issues.InvalidInstanceError(type_="asset", identifier=identifier, reason=str(e))
                    tracker.issue(error)
                    if stop_on_exception:
                        raise error.as_exception() from e
                    yield error
            yield _END_OF_CLASS

    def load_to_cdf(self, client: CogniteClient, dry_run: bool = False) -> Sequence[AssetWrite]:
        # generate assets
        # check for circular asset hierarchy
        # check for orphaned assets
        # batch upsert of assets to CDF (otherwise we will hit the API rate limit)

        raise NotImplementedError("Not implemented yet, this is placeholder")

    @classmethod
    def _check_for_circular_asset_hierarchy(cls, assets: list[AssetWrite]) -> None:
        """Check for circular references in the asset rules"""
        raise NotImplementedError("Not implemented yet, this is placeholder")

    @classmethod
    def _check_for_orphaned_assets(cls, assets: list[AssetWrite]) -> None:
        """Check for circular references in the asset rules"""
        raise NotImplementedError("Not implemented yet, this is placeholder")

    def _get_required_capabilities(self) -> list[Capability]:
        raise NotImplementedError("Not implemented yet, this is placeholder")

    def _upload_to_cdf(
        self,
        client: CogniteClient,
        items: list[AssetWrite],
        dry_run: bool,
        read_issues: NeatIssueList,
    ) -> Iterable[UploadResult]:
        raise NotImplementedError("Not implemented yet, this is placeholder")

    def write_to_file(self, filepath: Path) -> None:
        raise NotImplementedError("Not implemented yet, this is placeholder")


def _process_properties(properties: dict[str, list[str]], property_renaming_config: dict[str, str]) -> dict:
    metadata: dict[str, str] = defaultdict(str)
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
