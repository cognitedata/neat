from collections.abc import Iterable
from pathlib import Path
from typing import cast

from cognite.client import CogniteClient
from cognite.client.data_classes import Asset, AssetFilter, AssetList

from ._base import ClassicCDFBaseExtractor, InstanceIdPrefix


class AssetsExtractor(ClassicCDFBaseExtractor[Asset]):
    """Extract data from Cognite Data Fusions Assets into Neat."""

    _default_rdf_type = "Asset"
    _instance_id_prefix = InstanceIdPrefix.asset

    @classmethod
    def _from_dataset(cls, client: CogniteClient, data_set_external_id: str) -> tuple[int | None, Iterable[Asset]]:
        total = client.assets.aggregate_count(filter=AssetFilter(data_set_ids=[{"externalId": data_set_external_id}]))
        items = client.assets(data_set_external_ids=data_set_external_id)
        return total, items

    @classmethod
    def _from_hierarchy(cls, client: CogniteClient, root_asset_external_id: str) -> tuple[int | None, Iterable[Asset]]:
        total = client.assets.aggregate_count(
            filter=AssetFilter(asset_subtree_ids=[{"externalId": root_asset_external_id}])
        )
        items = cast(
            Iterable[Asset],
            client.assets(asset_subtree_external_ids=root_asset_external_id),
        )
        return total, items

    @classmethod
    def _from_file(cls, file_path: str | Path) -> tuple[int | None, Iterable[Asset]]:
        assets = AssetList.load(Path(file_path).read_text())
        return len(assets), assets
