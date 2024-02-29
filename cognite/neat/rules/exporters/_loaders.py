from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Generic, TypeVar, cast

from cognite.client import CogniteClient
from cognite.client.data_classes._base import (
    T_CogniteResourceList,
    T_WritableCogniteResource,
    T_WriteClass,
    WriteableCogniteResourceList,
)
from cognite.client.data_classes.data_modeling import (
    Container,
    ContainerApply,
    ContainerApplyList,
    ContainerList,
    DataModel,
    DataModelApply,
    DataModelApplyList,
    DataModelingId,
    DataModelList,
    Space,
    SpaceApply,
    SpaceApplyList,
    SpaceList,
    View,
    ViewApply,
    ViewApplyList,
    ViewList,
)
from cognite.client.data_classes.data_modeling.ids import (
    ContainerId,
    DataModelId,
    InstanceId,
    VersionedDataModelingId,
    ViewId,
)
from cognite.client.utils.useful_types import SequenceNotStr

T_ID = TypeVar("T_ID", bound=str | (int | (DataModelingId | (InstanceId | VersionedDataModelingId))))
T_WritableCogniteResourceList = TypeVar("T_WritableCogniteResourceList", bound=WriteableCogniteResourceList)


class ResourceLoader(
    ABC,
    Generic[T_ID, T_WriteClass, T_WritableCogniteResource, T_CogniteResourceList, T_WritableCogniteResourceList],
):
    resource_name: str

    def __init__(self, client: CogniteClient) -> None:
        self.client = client

    @classmethod
    @abstractmethod
    def get_id(cls, item: T_WriteClass | T_WritableCogniteResource) -> T_ID:
        raise NotImplementedError

    @classmethod
    def get_ids(cls, items: Sequence[T_WriteClass | T_WritableCogniteResource]) -> list[T_ID]:
        return [cls.get_id(item) for item in items]

    @abstractmethod
    def create(self, items: T_CogniteResourceList) -> T_WritableCogniteResourceList:
        raise NotImplementedError

    @abstractmethod
    def retrieve(self, ids: SequenceNotStr[T_ID]) -> T_WritableCogniteResourceList:
        raise NotImplementedError

    @abstractmethod
    def update(self, items: T_CogniteResourceList) -> T_WritableCogniteResourceList:
        raise NotImplementedError

    @abstractmethod
    def delete(self, ids: SequenceNotStr[T_ID]) -> list[T_ID]:
        raise NotImplementedError

    def are_equal(self, local: T_WriteClass, remote: T_WritableCogniteResource) -> bool:
        return local == remote.as_write()


class DataModelingLoader(
    ResourceLoader[T_ID, T_WriteClass, T_WritableCogniteResource, T_CogniteResourceList, T_WritableCogniteResourceList]
):
    def in_space(self, item: T_WriteClass | T_WritableCogniteResource, space: set[str]) -> bool:
        if hasattr(item, "space"):
            return item.space in space
        raise ValueError(f"Item {item} does not have a space attribute")


class SpaceLoader(DataModelingLoader[str, SpaceApply, Space, SpaceApplyList, SpaceList]):
    resource_name = "spaces"

    @classmethod
    def get_id(cls, item: Space | SpaceApply) -> str:
        return item.space

    def create(self, items: SpaceApplyList) -> SpaceList:
        return self.client.data_modeling.spaces.apply(items)

    def retrieve(self, ids: SequenceNotStr[str]) -> SpaceList:
        return self.client.data_modeling.spaces.retrieve(ids)

    def update(self, items: SpaceApplyList) -> SpaceList:
        return self.create(items)

    def delete(self, ids: SequenceNotStr[str]) -> list[str]:
        return self.client.data_modeling.spaces.delete(ids)


class ViewLoader(DataModelingLoader[ViewId, ViewApply, View, ViewApplyList, ViewList]):
    resource_name = "views"

    def __init__(self, client: CogniteClient):
        self.client = client
        self._interfaces_by_id: dict[ViewId, View] = {}

    @classmethod
    def get_id(cls, item: View | ViewApply) -> ViewId:
        return item.as_id()

    def create(self, items: ViewApplyList) -> ViewList:
        return self.client.data_modeling.views.apply(items)

    def retrieve(self, ids: SequenceNotStr[ViewId]) -> ViewList:
        return self.client.data_modeling.views.retrieve(cast(Sequence, ids))

    def update(self, items: ViewApplyList) -> ViewList:
        return self.create(items)

    def delete(self, ids: SequenceNotStr[ViewId]) -> list[ViewId]:
        return self.client.data_modeling.views.delete(cast(Sequence, ids))

    def are_equal(self, local: ViewApply, remote: View) -> bool:
        local_dumped = local.dump()
        cdf_resource_dumped = remote.as_write().dump()
        if not remote.implements:
            return local_dumped == cdf_resource_dumped

        if remote.properties:
            # All read version of views have all the properties of their parent views.
            # We need to remove these properties to compare with the local view.
            parents = self._retrieve_view_ancestors(remote.implements or [], self._interfaces_by_id)
            for parent in parents:
                for prop_name in parent.properties.keys():
                    cdf_resource_dumped["properties"].pop(prop_name, None)

        if not cdf_resource_dumped["properties"]:
            # All properties were removed, so we remove the properties key.
            cdf_resource_dumped.pop("properties", None)
        if "properties" in local_dumped and not local_dumped["properties"]:
            # In case the local properties are set to an empty dict.
            local_dumped.pop("properties", None)

        return local_dumped == cdf_resource_dumped

    def _retrieve_view_ancestors(self, parents: list[ViewId], cache: dict[ViewId, View]) -> list[View]:
        """Retrieves all ancestors of a view.

        This will mutate the cache passed in, and return a list of views that are the ancestors
        of the views in the parents list.

        Args:
            parents: The parents of the view to retrieve all ancestors for
            cache: The cache to store the views in
        """
        parent_ids = parents
        found: list[View] = []
        while parent_ids:
            to_lookup = []
            grand_parent_ids = []
            for parent in parent_ids:
                if parent in cache:
                    found.append(cache[parent])
                    grand_parent_ids.extend(cache[parent].implements or [])
                else:
                    to_lookup.append(parent)

            if to_lookup:
                looked_up = self.client.data_modeling.views.retrieve(to_lookup)
                cache.update({view.as_id(): view for view in looked_up})
                found.extend(looked_up)
                for view in looked_up:
                    grand_parent_ids.extend(view.implements or [])

            parent_ids = grand_parent_ids
        return found


class ContainerLoader(DataModelingLoader[ContainerId, ContainerApply, Container, ContainerApplyList, ContainerList]):
    resource_name = "containers"

    @classmethod
    def get_id(cls, item: Container | ContainerApply) -> ContainerId:
        return item.as_id()

    def create(self, items: ContainerApplyList) -> ContainerList:
        return self.client.data_modeling.containers.apply(items)

    def retrieve(self, ids: SequenceNotStr[ContainerId]) -> ContainerList:
        return self.client.data_modeling.containers.retrieve(cast(Sequence, ids))

    def update(self, items: ContainerApplyList) -> ContainerList:
        return self.create(items)

    def delete(self, ids: SequenceNotStr[ContainerId]) -> list[ContainerId]:
        return self.client.data_modeling.containers.delete(cast(Sequence, ids))


class DataModelLoader(DataModelingLoader[DataModelId, DataModelApply, DataModel, DataModelApplyList, DataModelList]):
    resource_name = "data_models"

    @classmethod
    def get_id(cls, item: DataModel | DataModelApply) -> DataModelId:
        return item.as_id()

    def create(self, items: DataModelApplyList) -> DataModelList:
        return self.client.data_modeling.data_models.apply(items)

    def retrieve(self, ids: SequenceNotStr[DataModelId]) -> DataModelList:
        return self.client.data_modeling.data_models.retrieve(cast(Sequence, ids))

    def update(self, items: DataModelApplyList) -> DataModelList:
        return self.create(items)

    def delete(self, ids: SequenceNotStr[DataModelId]) -> list[DataModelId]:
        return self.client.data_modeling.data_models.delete(cast(Sequence, ids))

    def are_equal(self, local: DataModelApply, remote: DataModel) -> bool:
        local_dumped = local.dump()
        cdf_resource_dumped = remote.as_write().dump()

        # Data models that have the same views, but in different order, are considered equal.
        # We also account for whether views are given as IDs or View objects.
        local_dumped["views"] = sorted(
            (v if isinstance(v, ViewId) else v.as_id()).as_tuple() for v in local.views or []
        )
        cdf_resource_dumped["views"] = sorted(
            (v if isinstance(v, ViewId) else v.as_id()).as_tuple() for v in remote.views or []
        )

        return local_dumped == cdf_resource_dumped
