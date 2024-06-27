from collections.abc import Sequence
from dataclasses import dataclass, fields

from cognite.client import CogniteClient
from cognite.client.data_classes import AssetWrite

from cognite.neat.graph._tracking.base import Tracker
from cognite.neat.graph._tracking.log import LogTracker
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.issues import NeatIssue, NeatIssueList
from cognite.neat.rules.models import AssetRules

from ._base import CDFLoader


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
    def __init__(
        self,
        rules: AssetRules,
        graph_store: NeatGraphStore,
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

    @classmethod
    def from_rules(
        cls,
        rules: AssetRules,
        graph_store: NeatGraphStore,
        data_set_id: int,
        use_orphanage: bool = False,
        use_labels: bool = False,
        asset_external_id_prefix: str | None = None,
        metadata_keys: AssetLoaderMetadataKeys | None = None,
    ) -> "AssetLoader":
        issues: list[NeatIssue] = []

        return cls(
            rules, graph_store, data_set_id, use_orphanage, use_labels, asset_external_id_prefix, metadata_keys, issues
        )

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
