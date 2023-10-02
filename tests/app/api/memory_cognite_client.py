from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from typing import Any, Literal, TypeVar

from cognite.client._constants import DEFAULT_LIMIT_READ
from cognite.client.data_classes import (
    Asset,
    AssetAggregate,
    AssetFilter,
    AssetHierarchy,
    AssetList,
    AssetUpdate,
    GeoLocationFilter,
    LabelDefinition,
    LabelDefinitionList,
    LabelFilter,
    Relationship,
    RelationshipFilter,
    RelationshipList,
    RelationshipUpdate,
    TimestampRange,
)
from cognite.client.data_classes._base import CogniteFilter, T_CogniteResource, T_CogniteResourceList
from cognite.client.data_classes.shared import AggregateBucketResult
from cognite.client.testing import monkeypatch_cognite_client
from cognite.client.utils._identifier import Identifier, IdentifierSequence, SingletonIdentifierSequence

ExternalId = str
ID = int

T = TypeVar("T")


class MemoryClient:
    _RESOURCE_PATH: str

    def __init__(self, list_cls: type[T_CogniteResourceList], cls: type[T_CogniteResource]) -> None:
        self.store: dict[ExternalId | ID, T_CogniteResource] = {}
        self._next_id = 1
        self._CREATE_LIMIT = 10_000
        self._RESOURCE_PATH = "assets"
        self.cls = cls
        self.list_cls = list_cls

        class Config:
            max_workers = 10

        self._config = Config()

    def _retrieve(
        self,
        identifier: Identifier,
        cls: type[T_CogniteResource],
        resource_path: str | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> T_CogniteResource | None:
        return self.store.get(identifier.as_primitive())

    def _retrieve_multiple(
        self,
        identifiers: SingletonIdentifierSequence | IdentifierSequence,
        resource_path: str | None = None,
        ignore_unknown_ids: bool | None = None,
        headers: dict[str, Any] | None = None,
        other_params: dict[str, Any] | None = None,
    ) -> T_CogniteResourceList | T_CogniteResource | None:
        if identifiers.is_singleton():
            return self._retrieve(identifier=identifiers[0], cls=self.cls)
        return self.list_cls([self._retrieve(identifier, cls=self.cls) for identifier in identifiers])

    def _list(
        self,
        method: Literal["POST", "GET"],
        resource_path: str | None = None,
        url_path: str | None = None,
        limit: int | None = None,
        filter: dict | None = None,
        other_params: dict | None = None,
        partitions: int | None = None,
        sort: Sequence[str] | None = None,
        headers: dict | None = None,
        initial_cursor: str | None = None,
    ) -> T_CogniteResourceList:
        return self.list_cls(self._list_unique_in_store())

    def _list_unique_in_store(self) -> T_CogniteResourceList:
        unique_ids = {id(item): item for item in self.store.values()}
        return self.list_cls(unique_ids.values())

    def dump(self, ordered: bool = False, exclude: set[str] | None = None) -> list[dict]:
        exclude = exclude or set()
        iterable = (self._dump_item(item, ordered, exclude) for item in self._list_unique_in_store())
        if ordered:
            return sorted(iterable, key=lambda x: x["external_id"])
        return list(iterable)

    @classmethod
    def _dump_item(cls, item: T_CogniteResource, ordered: bool, exclude: set[str]) -> dict[str, Any]:
        dump = item.dump()
        if ordered and "metadata" in dump:
            for key, value in list(dump["metadata"].items()):
                if isinstance(value, list):
                    dump["metadata"][key] = sorted(value)

        if "labels" in dump:
            # Labels are not properly dumped to dict.
            iterable = (label.dump() if hasattr(label, "dump") else label for label in dump["labels"])
            dump["labels"] = sorted(iterable, key=lambda x: x["externalId"]) if ordered else list(iterable)
        if exclude:
            for to_exclude in exclude:
                keys = to_exclude.split(".")
                dump_from = dump
                with suppress(KeyError):
                    for key in keys[:-1]:
                        dump_from = dump_from[key]
                    dump_from.pop(keys[-1])
        return dump

    def _aggregate(
        self,
        cls: type[T],
        resource_path: str | None = None,
        filter: CogniteFilter | dict | None = None,
        aggregate: str | None = None,
        fields: Sequence[str] | None = None,
        keys: Sequence[str] | None = None,
        headers: dict | None = None,
    ) -> list[T]:
        raise NotImplementedError()

    def _create_multiple(
        self,
        items: Sequence[T_CogniteResource] | Sequence[dict[str, Any]] | T_CogniteResource | dict[str, Any],
        resource_path: str | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        extra_body_fields: dict | None = None,
        limit: int | None = None,
    ) -> T_CogniteResourceList | T_CogniteResource:
        is_single = not isinstance(items, Sequence)
        create_items = [items] if is_single else items
        for item in create_items:
            self.store[item.external_id] = item
        return create_items


class AssetsMemory(MemoryClient):
    def __init__(self):
        super().__init__(AssetList, Asset)

    def __call__(
        self,
        chunk_size: int | None = None,
        name: str | None = None,
        parent_ids: Sequence[int] | None = None,
        parent_external_ids: Sequence[str] | None = None,
        asset_subtree_ids: int | Sequence[int] | None = None,
        asset_subtree_external_ids: str | Sequence[str] | None = None,
        metadata: dict[str, str] | None = None,
        data_set_ids: int | Sequence[int] | None = None,
        data_set_external_ids: str | Sequence[str] | None = None,
        labels: LabelFilter = None,
        geo_location: GeoLocationFilter = None,
        source: str | None = None,
        created_time: dict[str, Any] | TimestampRange = None,
        last_updated_time: dict[str, Any] | TimestampRange = None,
        root: bool | None = None,
        external_id_prefix: str | None = None,
        aggregated_properties: Sequence[str] | None = None,
        limit: int | None = None,
        partitions: int | None = None,
    ) -> Iterator[Asset] | Iterator[AssetList]:
        return iter(self._list(method="POST"))

    def retrieve(self, id: int | None = None, external_id: str | None = None) -> Asset | None:
        identifier = IdentifierSequence.load(ids=id, external_ids=external_id).as_singleton()
        return self._retrieve_multiple(identifiers=identifier)

    def retrieve_multiple(
        self,
        ids: Sequence[int] | None = None,
        external_ids: Sequence[str] | None = None,
        ignore_unknown_ids: bool = False,
    ) -> AssetList:
        identifiers = IdentifierSequence.load(ids=ids, external_ids=external_ids)
        return self._retrieve_multiple(identifiers=identifiers, ignore_unknown_ids=ignore_unknown_ids)

    def aggregate(self, filter: AssetFilter | dict = None) -> list[AssetAggregate]:
        return [AssetAggregate(count=len(self._list_unique_in_store()))]

    def aggregate_metadata_keys(self, filter: AssetFilter | dict = None) -> Sequence[AggregateBucketResult]:
        raise NotImplementedError()

    def aggregate_metadata_values(
        self, keys: Sequence[str], filter: AssetFilter | dict = None
    ) -> Sequence[AggregateBucketResult]:
        raise NotImplementedError()

    def create(self, asset: Asset | Sequence[Asset]) -> Asset | AssetList:
        return self._create_multiple(items=asset)

    def create_hierarchy(
        self,
        assets: Sequence[Asset] | AssetHierarchy,
        *,
        upsert: bool = False,
        upsert_mode: Literal["patch", "replace"] = "patch",
    ) -> AssetList:
        if isinstance(assets, AssetHierarchy):
            raise NotImplementedError()

        return self.create(assets)

    def delete(
        self,
        id: int | Sequence[int] | None = None,
        external_id: str | Sequence[str] | None = None,
        recursive: bool = False,
        ignore_unknown_ids: bool = False,
    ) -> None:
        raise NotImplementedError()

    def update(self, item: Asset | AssetUpdate | Sequence[Asset | AssetUpdate]) -> Asset | AssetList:
        raise NotImplementedError()

    def search(
        self,
        name: str | None = None,
        description: str | None = None,
        query: str | None = None,
        filter: AssetFilter | dict = None,
        limit: int = 100,
    ) -> AssetList:
        raise NotImplementedError()

    def retrieve_subtree(
        self, id: int | None = None, external_id: str | None = None, depth: int | None = None
    ) -> AssetList:
        raise NotImplementedError()

    def list(
        self,
        name: str | None = None,
        parent_ids: Sequence[int] | None = None,
        parent_external_ids: Sequence[str] | None = None,
        asset_subtree_ids: int | Sequence[int] | None = None,
        asset_subtree_external_ids: str | Sequence[str] | None = None,
        data_set_ids: int | Sequence[int] | None = None,
        data_set_external_ids: str | Sequence[str] | None = None,
        labels: LabelFilter = None,
        geo_location: GeoLocationFilter = None,
        metadata: dict[str, str] | None = None,
        source: str | None = None,
        created_time: dict[str, Any] | TimestampRange = None,
        last_updated_time: dict[str, Any] | TimestampRange = None,
        root: bool | None = None,
        external_id_prefix: str | None = None,
        aggregated_properties: Sequence[str] | None = None,
        partitions: int | None = None,
        limit: int = DEFAULT_LIMIT_READ,
    ) -> AssetList:
        return self._list(method="POST")


class RelationshipsMemory(MemoryClient):
    def __init__(self):
        super().__init__(RelationshipList, Relationship)

    def _create_filter(
        self,
        source_external_ids: Sequence[str] | None = None,
        source_types: Sequence[str] | None = None,
        target_external_ids: Sequence[str] | None = None,
        target_types: Sequence[str] | None = None,
        data_set_ids: Sequence[dict[str, Any]] | None = None,
        start_time: dict[str, int] | None = None,
        end_time: dict[str, int] | None = None,
        confidence: dict[str, int] | None = None,
        last_updated_time: dict[str, int] | None = None,
        created_time: dict[str, int] | None = None,
        active_at_time: dict[str, int] | None = None,
        labels: LabelFilter = None,
    ) -> dict[str, Any]:
        return RelationshipFilter(
            source_external_ids=source_external_ids,
            source_types=source_types,
            target_external_ids=target_external_ids,
            target_types=target_types,
            data_set_ids=data_set_ids,
            start_time=start_time,
            end_time=end_time,
            confidence=confidence,
            last_updated_time=last_updated_time,
            created_time=created_time,
            active_at_time=active_at_time,
            labels=labels,
        ).dump(camel_case=True)

    def __call__(
        self,
        source_external_ids: Sequence[str] | None = None,
        source_types: Sequence[str] | None = None,
        target_external_ids: Sequence[str] | None = None,
        target_types: Sequence[str] | None = None,
        data_set_ids: int | Sequence[int] | None = None,
        data_set_external_ids: str | Sequence[str] | None = None,
        start_time: dict[str, int] | None = None,
        end_time: dict[str, int] | None = None,
        confidence: dict[str, int] | None = None,
        last_updated_time: dict[str, int] | None = None,
        created_time: dict[str, int] | None = None,
        active_at_time: dict[str, int] | None = None,
        labels: LabelFilter = None,
        limit: int | None = None,
        fetch_resources: bool = False,
        chunk_size: int | None = None,
        partitions: int | None = None,
    ) -> Iterator[Relationship] | Iterator[RelationshipList]:
        return iter(self._list(method="POST"))

    def retrieve(self, external_id: str, fetch_resources: bool = False) -> Relationship | None:
        identifiers = IdentifierSequence.load(ids=None, external_ids=external_id).as_singleton()
        return self._retrieve_multiple(identifiers=identifiers)

    def retrieve_multiple(self, external_ids: Sequence[str], fetch_resources: bool = False) -> RelationshipList:
        identifiers = IdentifierSequence.load(ids=None, external_ids=external_ids)
        return self._retrieve_multiple(identifiers=identifiers)

    def create(self, relationship: Relationship | Sequence[Relationship]) -> Relationship | RelationshipList:
        if isinstance(relationship, Sequence):
            relationship = [r._validate_resource_types() for r in relationship]
        else:
            relationship = relationship._validate_resource_types()

        return self._create_multiple(items=relationship)

    def update(
        self, item: Relationship | RelationshipUpdate | Sequence[Relationship | RelationshipUpdate]
    ) -> Relationship | RelationshipList:
        raise NotImplementedError()
        # return self._update_multiple(

    def delete(self, external_id: str | Sequence[str], ignore_unknown_ids: bool = False) -> None:
        raise NotImplementedError()
        # self._delete_multiple(

    def list(
        self,
        source_external_ids: Sequence[str] | None = None,
        source_types: Sequence[str] | None = None,
        target_external_ids: Sequence[str] | None = None,
        target_types: Sequence[str] | None = None,
        data_set_ids: int | Sequence[int] | None = None,
        data_set_external_ids: str | Sequence[str] | None = None,
        start_time: dict[str, int] | None = None,
        end_time: dict[str, int] | None = None,
        confidence: dict[str, int] | None = None,
        last_updated_time: dict[str, int] | None = None,
        created_time: dict[str, int] | None = None,
        active_at_time: dict[str, int] | None = None,
        labels: LabelFilter = None,
        limit: int = 100,
        partitions: int | None = None,
        fetch_resources: bool = False,
    ) -> RelationshipList:
        return self._list(method="POST")


class LabelsMemory(MemoryClient):
    _RESOURCE_PATH = "/labels"

    def __init__(self):
        super().__init__(LabelDefinitionList, LabelDefinition)

    def __call__(
        self,
        name: str | None = None,
        external_id_prefix: str | None = None,
        limit: int | None = None,
        chunk_size: int | None = None,
        data_set_ids: int | Sequence[int] | None = None,
        data_set_external_ids: str | Sequence[str] | None = None,
    ) -> Iterator[LabelDefinition] | Iterator[LabelDefinitionList]:
        return iter(self._list(method="POST"))

    def create(self, label: LabelDefinition | Sequence[LabelDefinition]) -> LabelDefinition | LabelDefinitionList:
        if isinstance(label, Sequence):
            if len(label) > 0 and not isinstance(label[0], LabelDefinition):
                raise TypeError("'label' must be of type LabelDefinition or Sequence[LabelDefinition]")
        elif not isinstance(label, LabelDefinition):
            raise TypeError("'label' must be of type LabelDefinition or Sequence[LabelDefinition]")
        return self._create_multiple(items=label)

    def delete(self, external_id: str | Sequence[str] | None = None) -> None:
        raise NotImplementedError()

    def list(
        self,
        name: str | None = None,
        external_id_prefix: str | None = None,
        data_set_ids: int | Sequence[int] | None = None,
        data_set_external_ids: str | Sequence[str] | None = None,
        limit: int = DEFAULT_LIMIT_READ,
    ) -> LabelDefinitionList:
        return self._list(method="POST", limit=limit)


@contextmanager
def memory_cognite_client():
    with monkeypatch_cognite_client() as client:
        client.assets = AssetsMemory()
        client.relationships = RelationshipsMemory()
        client.labels = LabelsMemory()
        yield client
