from collections.abc import Callable, Set
from datetime import datetime, timezone
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import Event, EventFilter, EventList
from rdflib import RDF, Literal, Namespace

from cognite.neat._graph.models import Triple

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix


class EventsExtractor(ClassicCDFBaseExtractor[Event]):
    """Extract data from Cognite Data Fusions Events into Neat.

    Args:
        items (Iterable[Event]): An iterable of items.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        to_type (Callable[[Event], str | None], optional): A function to convert an item to a type.
            Defaults to None. If None or if the function returns None, the asset will be set to the default type.
        total (int, optional): The total number of items to load. If passed, you will get a progress bar if rich
            is installed. Defaults to None.
        limit (int, optional): The maximal number of items to load. Defaults to None. This is typically used for
            testing setup of the extractor. For example, if you are extracting 100 000 assets, you might want to
            limit the extraction to 1000 assets to test the setup.
        unpack_metadata (bool, optional): Whether to unpack metadata. Defaults to False, which yields the metadata as
            a JSON string.
        skip_metadata_values (set[str] | frozenset[str] | None, optional): If you are unpacking metadata, then
           values in this set will be skipped.
    """

    _default_rdf_type = "Event"

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

    def _item2triples(self, event: Event) -> list[Triple]:
        id_ = self.namespace[f"{InstanceIdPrefix.event}{event.id}"]

        type_ = self._get_rdf_type(event)

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, self.namespace[type_])]

        # Create attributes

        if event.external_id:
            triples.append((id_, self.namespace.external_id, Literal(event.external_id)))

        if event.source:
            triples.append((id_, self.namespace.type, Literal(event.source)))

        if event.type:
            triples.append((id_, self.namespace.type, Literal(event.type)))

        if event.subtype:
            triples.append((id_, self.namespace.subtype, Literal(event.subtype)))

        if event.metadata:
            triples.extend(self._metadata_to_triples(id_, event.metadata))

        if event.description:
            triples.append((id_, self.namespace.description, Literal(event.description)))

        if event.created_time:
            triples.append(
                (
                    id_,
                    self.namespace.created_time,
                    Literal(datetime.fromtimestamp(event.created_time / 1000, timezone.utc)),
                )
            )

        if event.last_updated_time:
            triples.append(
                (
                    id_,
                    self.namespace.last_updated_time,
                    Literal(datetime.fromtimestamp(event.last_updated_time / 1000, timezone.utc)),
                )
            )

        if event.start_time:
            triples.append(
                (
                    id_,
                    self.namespace.start_time,
                    Literal(datetime.fromtimestamp(event.start_time / 1000, timezone.utc)),
                )
            )

        if event.end_time:
            triples.append(
                (
                    id_,
                    self.namespace.end_time,
                    Literal(datetime.fromtimestamp(event.end_time / 1000, timezone.utc)),
                )
            )

        if event.data_set_id:
            triples.append(
                (
                    id_,
                    self.namespace.data_set_id,
                    self.namespace[f"{InstanceIdPrefix.data_set}{event.data_set_id}"],
                )
            )

        if event.asset_ids:
            for asset_id in event.asset_ids:
                triples.append((id_, self.namespace.asset, self.namespace[f"{InstanceIdPrefix.asset}{asset_id}"]))

        return triples
