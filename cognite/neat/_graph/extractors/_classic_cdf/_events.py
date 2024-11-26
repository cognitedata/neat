from collections.abc import Iterable
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Event, EventFilter, EventList

from ._base import ClassicCDFBaseExtractor, InstanceIdPrefix


class EventsExtractor(ClassicCDFBaseExtractor[Event]):
    """Extract data from Cognite Data Fusions Events into Neat."""

    _default_rdf_type = "Event"
    _instance_id_prefix = InstanceIdPrefix.event

    @classmethod
    def _from_dataset(cls, client: CogniteClient, data_set_external_id: str) -> tuple[int | None, Iterable[Event]]:
        total = client.events.aggregate_count(filter=EventFilter(data_set_ids=[{"externalId": data_set_external_id}]))
        items = client.events(data_set_external_ids=data_set_external_id)
        return total, items

    @classmethod
    def _from_hierarchy(cls, client: CogniteClient, root_asset_external_id: str) -> tuple[int | None, Iterable[Event]]:
        total = client.events.aggregate_count(
            filter=EventFilter(asset_subtree_ids=[{"externalId": root_asset_external_id}])
        )
        items = client.events(asset_subtree_external_ids=[root_asset_external_id])
        return total, items

    @classmethod
    def _from_file(cls, file_path: str | Path) -> tuple[int | None, Iterable[Event]]:
        assets = EventList.load(Path(file_path).read_text())
        return len(assets), assets
