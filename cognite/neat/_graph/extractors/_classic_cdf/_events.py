from collections.abc import Callable, Set
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Event, EventFilter, EventList
from rdflib import Namespace

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix


class EventsExtractor(ClassicCDFBaseExtractor[Event]):
    """Extract data from Cognite Data Fusions Events into Neat."""

    _default_rdf_type = "Event"
    _instance_id_prefix = InstanceIdPrefix.event

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Event], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        total = client.events.aggregate_count(filter=EventFilter(data_set_ids=[{"externalId": data_set_external_id}]))

        return cls(
            client.events(data_set_external_ids=data_set_external_id),
            namespace,
            to_type,
            total=total,
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    @classmethod
    def from_hierarchy(
        cls,
        client: CogniteClient,
        root_asset_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Event], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        total = client.events.aggregate_count(
            filter=EventFilter(asset_subtree_ids=[{"externalId": root_asset_external_id}])
        )

        return cls(
            client.events(asset_subtree_external_ids=[root_asset_external_id]),
            namespace,
            to_type,
            total,
            limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Event], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        events = EventList.load(Path(file_path).read_text())

        return cls(
            events,
            namespace,
            to_type,
            total=len(events),
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )
