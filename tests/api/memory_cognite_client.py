from contextlib import contextmanager
from typing import Any, Iterator, List, Literal, Optional, Sequence, Type, TypeVar, Union

from cognite.client._constants import LIST_LIMIT_DEFAULT
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

    def __init__(self, *_, **__) -> None:
        self.store: dict[ExternalId | ID, T_CogniteResource] = {}
        self._next_id = 1
        self._CREATE_LIMIT = 10_000
        self._RESOURCE_PATH = "assets"

        class Config:
            max_workers = 10

        self._config = Config()

    def _retrieve(
        self,
        identifier: Identifier,
        cls: Type[T_CogniteResource],
        resource_path: str = None,
        params: dict = None,
        headers: dict = None,
    ) -> Optional[T_CogniteResource]:
        return self.store.get(identifier.as_primitive())

    def _retrieve_multiple(
        self,
        list_cls: Type[T_CogniteResourceList],
        resource_cls: Type[T_CogniteResource],
        identifiers: Union[SingletonIdentifierSequence, IdentifierSequence],
        resource_path: Optional[str] = None,
        ignore_unknown_ids: Optional[bool] = None,
        headers: Optional[dict[str, Any]] = None,
        other_params: Optional[dict[str, Any]] = None,
    ) -> Union[T_CogniteResourceList, Optional[T_CogniteResource]]:
        if identifiers.is_singleton():
            return self._retrieve(identifier=identifiers[0], cls=Asset)
        return list_cls([self._retrieve(identifier, cls=Asset) for identifier in identifiers])

    def _list(
        self,
        method: Literal["POST", "GET"],
        list_cls: Type[T_CogniteResourceList],
        resource_cls: Type[T_CogniteResource],
        resource_path: Optional[str] = None,
        url_path: Optional[str] = None,
        limit: Optional[int] = None,
        filter: Optional[dict] = None,
        other_params: Optional[dict] = None,
        partitions: Optional[int] = None,
        sort: Optional[Sequence[str]] = None,
        headers: Optional[dict] = None,
        initial_cursor: Optional[str] = None,
    ) -> T_CogniteResourceList:
        return list_cls(self.list_unique_in_store(list_cls))

    def list_unique_in_store(self, list_cls: Type[T_CogniteResourceList]) -> T_CogniteResourceList:
        unique_ids = {id(item): item for item in self.store.values()}
        return list_cls(unique_ids.values())

    def _aggregate(
        self,
        cls: Type[T],
        resource_path: Optional[str] = None,
        filter: Optional[Union[CogniteFilter, dict]] = None,
        aggregate: Optional[str] = None,
        fields: Optional[Sequence[str]] = None,
        keys: Optional[Sequence[str]] = None,
        headers: Optional[dict] = None,
    ) -> list[T]:
        raise NotImplementedError()

    def _create_multiple(
        self,
        items: Sequence[T_CogniteResource] | Sequence[dict[str, Any]] | T_CogniteResource | dict[str, Any],
        list_cls: Type[T_CogniteResourceList],
        resource_cls: Type[T_CogniteResource],
        resource_path: Optional[str] = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        extra_body_fields: Optional[dict] = None,
        limit: Optional[int] = None,
    ) -> Union[T_CogniteResourceList, T_CogniteResource]:
        is_single = not isinstance(items, Sequence)
        create_items = [items] if is_single else items
        for item in create_items:
            if hasattr(item, "id") and item.id is None:
                item.id = self._next_id
                self._next_id += 1
                self.store[item.id] = item
            if hasattr(item, "external_id") and item.external_id is not None:
                self.store[item.external_id] = item
        return create_items


class AssetsMemory(MemoryClient):
    def __call__(
        self,
        chunk_size: int = None,
        name: str = None,
        parent_ids: Sequence[int] = None,
        parent_external_ids: Sequence[str] = None,
        asset_subtree_ids: Union[int, Sequence[int]] = None,
        asset_subtree_external_ids: Union[str, Sequence[str]] = None,
        metadata: dict[str, str] = None,
        data_set_ids: Union[int, Sequence[int]] = None,
        data_set_external_ids: Union[str, Sequence[str]] = None,
        labels: LabelFilter = None,
        geo_location: GeoLocationFilter = None,
        source: str = None,
        created_time: Union[dict[str, Any], TimestampRange] = None,
        last_updated_time: Union[dict[str, Any], TimestampRange] = None,
        root: bool = None,
        external_id_prefix: str = None,
        aggregated_properties: Sequence[str] = None,
        limit: int = None,
        partitions: int = None,
    ) -> Union[Iterator[Asset], Iterator[AssetList]]:
        return iter(
            self._list(
                method="POST",
                list_cls=AssetList,
                resource_cls=Asset,
            )
        )

    def retrieve(self, id: Optional[int] = None, external_id: Optional[str] = None) -> Optional[Asset]:
        identifier = IdentifierSequence.load(ids=id, external_ids=external_id).as_singleton()
        return self._retrieve_multiple(list_cls=AssetList, resource_cls=Asset, identifiers=identifier)

    def retrieve_multiple(
        self,
        ids: Optional[Sequence[int]] = None,
        external_ids: Optional[Sequence[str]] = None,
        ignore_unknown_ids: bool = False,
    ) -> AssetList:
        identifiers = IdentifierSequence.load(ids=ids, external_ids=external_ids)
        return self._retrieve_multiple(
            list_cls=AssetList, resource_cls=Asset, identifiers=identifiers, ignore_unknown_ids=ignore_unknown_ids
        )

    def list(
        self,
        name: str = None,
        parent_ids: Sequence[int] = None,
        parent_external_ids: Sequence[str] = None,
        asset_subtree_ids: Union[int, Sequence[int]] = None,
        asset_subtree_external_ids: Union[str, Sequence[str]] = None,
        data_set_ids: Union[int, Sequence[int]] = None,
        data_set_external_ids: Union[str, Sequence[str]] = None,
        labels: LabelFilter = None,
        geo_location: GeoLocationFilter = None,
        metadata: dict[str, str] = None,
        source: str = None,
        created_time: Union[dict[str, Any], TimestampRange] = None,
        last_updated_time: Union[dict[str, Any], TimestampRange] = None,
        root: bool = None,
        external_id_prefix: str = None,
        aggregated_properties: Sequence[str] = None,
        partitions: int = None,
        limit: int = LIST_LIMIT_DEFAULT,
    ) -> AssetList:
        return self._list(
            method="POST",
            list_cls=AssetList,
            resource_cls=Asset,
        )

    def aggregate(self, filter: Union[AssetFilter, dict] = None) -> List[AssetAggregate]:
        return [AssetAggregate(count=len(self.list_unique_in_store(AssetList)))]

    def aggregate_metadata_keys(self, filter: Union[AssetFilter, dict] = None) -> Sequence[AggregateBucketResult]:
        raise NotImplementedError()

    def aggregate_metadata_values(
        self, keys: Sequence[str], filter: Union[AssetFilter, dict] = None
    ) -> Sequence[AggregateBucketResult]:
        raise NotImplementedError()

    def create(self, asset: Union[Asset, Sequence[Asset]]) -> Union[Asset, AssetList]:
        return self._create_multiple(list_cls=AssetList, resource_cls=Asset, items=asset)

    def create_hierarchy(
        self,
        assets: Union[Sequence[Asset], AssetHierarchy],
        *,
        upsert: bool = False,
        upsert_mode: Literal["patch", "replace"] = "patch",
    ) -> AssetList:
        if isinstance(assets, AssetHierarchy):
            raise NotImplementedError()

        return self.create(assets)

    def delete(
        self,
        id: Union[int, Sequence[int]] = None,
        external_id: Union[str, Sequence[str]] = None,
        recursive: bool = False,
        ignore_unknown_ids: bool = False,
    ) -> None:
        raise NotImplementedError()

    def update(self, item: Union[Asset, AssetUpdate, Sequence[Union[Asset, AssetUpdate]]]) -> Union[Asset, AssetList]:
        raise NotImplementedError()

    def search(
        self,
        name: str = None,
        description: str = None,
        query: str = None,
        filter: Union[AssetFilter, dict] = None,
        limit: int = 100,
    ) -> AssetList:
        raise NotImplementedError()

    def retrieve_subtree(self, id: int = None, external_id: str = None, depth: int = None) -> AssetList:
        raise NotImplementedError()


class RelationshipsMemory(MemoryClient):
    def _create_filter(
        self,
        source_external_ids: Sequence[str] = None,
        source_types: Sequence[str] = None,
        target_external_ids: Sequence[str] = None,
        target_types: Sequence[str] = None,
        data_set_ids: Sequence[dict[str, Any]] = None,
        start_time: dict[str, int] = None,
        end_time: dict[str, int] = None,
        confidence: dict[str, int] = None,
        last_updated_time: dict[str, int] = None,
        created_time: dict[str, int] = None,
        active_at_time: dict[str, int] = None,
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
        source_external_ids: Sequence[str] = None,
        source_types: Sequence[str] = None,
        target_external_ids: Sequence[str] = None,
        target_types: Sequence[str] = None,
        data_set_ids: Union[int, Sequence[int]] = None,
        data_set_external_ids: Union[str, Sequence[str]] = None,
        start_time: dict[str, int] = None,
        end_time: dict[str, int] = None,
        confidence: dict[str, int] = None,
        last_updated_time: dict[str, int] = None,
        created_time: dict[str, int] = None,
        active_at_time: dict[str, int] = None,
        labels: LabelFilter = None,
        limit: int = None,
        fetch_resources: bool = False,
        chunk_size: int = None,
        partitions: int = None,
    ) -> Union[Iterator[Relationship], Iterator[RelationshipList]]:
        return iter(
            self._list(
                list_cls=RelationshipList,
                resource_cls=Relationship,
                method="POST",
            )
        )

    def retrieve(self, external_id: str, fetch_resources: bool = False) -> Optional[Relationship]:
        identifiers = IdentifierSequence.load(ids=None, external_ids=external_id).as_singleton()
        return self._retrieve_multiple(
            list_cls=RelationshipList,
            resource_cls=Relationship,
            identifiers=identifiers,
        )

    def retrieve_multiple(self, external_ids: Sequence[str], fetch_resources: bool = False) -> RelationshipList:
        identifiers = IdentifierSequence.load(ids=None, external_ids=external_ids)
        return self._retrieve_multiple(
            list_cls=RelationshipList,
            resource_cls=Relationship,
            identifiers=identifiers,
        )

    def list(
        self,
        source_external_ids: Sequence[str] = None,
        source_types: Sequence[str] = None,
        target_external_ids: Sequence[str] = None,
        target_types: Sequence[str] = None,
        data_set_ids: Union[int, Sequence[int]] = None,
        data_set_external_ids: Union[str, Sequence[str]] = None,
        start_time: dict[str, int] = None,
        end_time: dict[str, int] = None,
        confidence: dict[str, int] = None,
        last_updated_time: dict[str, int] = None,
        created_time: dict[str, int] = None,
        active_at_time: dict[str, int] = None,
        labels: LabelFilter = None,
        limit: int = 100,
        partitions: int = None,
        fetch_resources: bool = False,
    ) -> RelationshipList:
        return self._list(
            list_cls=RelationshipList,
            resource_cls=Relationship,
            method="POST",
        )

    def create(
        self, relationship: Union[Relationship, Sequence[Relationship]]
    ) -> Union[Relationship, RelationshipList]:
        if isinstance(relationship, Sequence):
            relationship = [r._validate_resource_types() for r in relationship]
        else:
            relationship = relationship._validate_resource_types()

        return self._create_multiple(list_cls=RelationshipList, resource_cls=Relationship, items=relationship)

    def update(
        self, item: Union[Relationship, RelationshipUpdate, Sequence[Union[Relationship, RelationshipUpdate]]]
    ) -> Union[Relationship, RelationshipList]:
        raise NotImplementedError()
        # return self._update_multiple(
        #     list_cls=RelationshipList, resource_cls=Relationship, update_cls=RelationshipUpdate, items=item
        # )

    def delete(self, external_id: Union[str, Sequence[str]], ignore_unknown_ids: bool = False) -> None:
        raise NotImplementedError()
        # self._delete_multiple(
        #     identifiers=IdentifierSequence.load(external_ids=external_id),
        #     wrap_ids=True,
        #     extra_body_fields={"ignoreUnknownIds": ignore_unknown_ids},
        # )


class LabelsMemory(MemoryClient):
    _RESOURCE_PATH = "/labels"

    def __call__(
        self,
        name: str = None,
        external_id_prefix: str = None,
        limit: int = None,
        chunk_size: int = None,
        data_set_ids: Union[int, Sequence[int]] = None,
        data_set_external_ids: Union[str, Sequence[str]] = None,
    ) -> Union[Iterator[LabelDefinition], Iterator[LabelDefinitionList]]:
        return iter(
            self._list(
                list_cls=LabelDefinitionList,
                resource_cls=LabelDefinition,
                method="POST",
            )
        )

    def list(
        self,
        name: str = None,
        external_id_prefix: str = None,
        data_set_ids: Union[int, Sequence[int]] = None,
        data_set_external_ids: Union[str, Sequence[str]] = None,
        limit: int = LIST_LIMIT_DEFAULT,
    ) -> LabelDefinitionList:
        return self._list(list_cls=LabelDefinitionList, resource_cls=LabelDefinition, method="POST", limit=limit)

    def create(
        self, label: Union[LabelDefinition, Sequence[LabelDefinition]]
    ) -> Union[LabelDefinition, LabelDefinitionList]:
        if isinstance(label, Sequence):
            if len(label) > 0 and not isinstance(label[0], LabelDefinition):
                raise TypeError("'label' must be of type LabelDefinition or Sequence[LabelDefinition]")
        elif not isinstance(label, LabelDefinition):
            raise TypeError("'label' must be of type LabelDefinition or Sequence[LabelDefinition]")
        return self._create_multiple(list_cls=LabelDefinitionList, resource_cls=LabelDefinition, items=label)

    def delete(self, external_id: Union[str, Sequence[str]] = None) -> None:
        raise NotImplementedError()
        # self._delete_multiple(identifiers=IdentifierSequence.load(external_ids=external_id), wrap_ids=True)


@contextmanager
def memory_cognite_client():
    with monkeypatch_cognite_client() as client:
        client.assets = AssetsMemory()
        client.relationships = RelationshipsMemory()
        client.labels = LabelsMemory()
        yield client
