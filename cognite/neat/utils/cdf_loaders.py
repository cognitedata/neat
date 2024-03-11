import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from graphlib import TopologicalSorter
from typing import Any, Generic, Literal, TypeVar, cast

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
    RequiresConstraint,
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
from cognite.client.exceptions import CogniteAPIError
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
    def create(self, items: Sequence[T_WriteClass]) -> T_WritableCogniteResourceList:
        raise NotImplementedError

    @abstractmethod
    def retrieve(self, ids: SequenceNotStr[T_ID]) -> T_WritableCogniteResourceList:
        raise NotImplementedError

    @abstractmethod
    def update(self, items: Sequence[T_WriteClass]) -> T_WritableCogniteResourceList:
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

    def sort_by_dependencies(self, items: list[T_WriteClass]) -> list[T_WriteClass]:
        return items


class SpaceLoader(DataModelingLoader[str, SpaceApply, Space, SpaceApplyList, SpaceList]):
    resource_name = "spaces"

    @classmethod
    def get_id(cls, item: Space | SpaceApply) -> str:
        return item.space

    def create(self, items: Sequence[SpaceApply]) -> SpaceList:
        return self.client.data_modeling.spaces.apply(items)

    def retrieve(self, ids: SequenceNotStr[str]) -> SpaceList:
        return self.client.data_modeling.spaces.retrieve(ids)

    def update(self, items: Sequence[SpaceApply]) -> SpaceList:
        return self.create(items)

    def delete(self, ids: SequenceNotStr[str]) -> list[str]:
        return self.client.data_modeling.spaces.delete(ids)


class ViewLoader(DataModelingLoader[ViewId, ViewApply, View, ViewApplyList, ViewList]):
    resource_name = "views"

    def __init__(self, client: CogniteClient, existing_handling: Literal["fail", "skip", "update", "force"] = "fail"):
        self.client = client
        self.existing_handling = existing_handling
        self._interfaces_by_id: dict[ViewId, View] = {}

    @classmethod
    def get_id(cls, item: View | ViewApply) -> ViewId:
        return item.as_id()

    def create(self, items: Sequence[ViewApply]) -> ViewList:
        try:
            return self.client.data_modeling.views.apply(items)
        except CogniteAPIError as e:
            if self.existing_handling == "force" and e.message.startswith("Cannot update view"):
                res = re.search(r"(?<=\')(.*?)(?=\')", e.message)
                if res is None or ":" not in res.group(1) or "/" not in res.group(1):
                    raise e
                view_id_str = res.group(1)
                space, external_id_version = view_id_str.split(":")
                external_id, version = external_id_version.split("/")
                self.delete([ViewId(space, external_id, version)])
                return self.create(items)
            raise e

    def retrieve(self, ids: SequenceNotStr[ViewId]) -> ViewList:
        return self.client.data_modeling.views.retrieve(cast(Sequence, ids))

    def update(self, items: Sequence[ViewApply]) -> ViewList:
        return self.create(items)

    def delete(self, ids: SequenceNotStr[ViewId]) -> list[ViewId]:
        return self.client.data_modeling.views.delete(cast(Sequence, ids))

    def _as_write_raw(self, view: View) -> dict[str, Any]:
        dumped = view.as_write().dump()
        if view.properties:
            # All read version of views have all the properties of their parent views.
            # We need to remove these properties to compare with the local view.
            parents = self._retrieve_view_ancestors(view.implements or [], self._interfaces_by_id)
            for parent in parents:
                for prop_name in parent.properties.keys():
                    dumped["properties"].pop(prop_name, None)

        if not dumped["properties"]:
            # All properties were removed, so we remove the properties key.
            dumped.pop("properties", None)
        return dumped

    def are_equal(self, local: ViewApply, remote: View) -> bool:
        local_dumped = local.dump()
        if not remote.implements:
            return local_dumped == remote.as_write().dump()

        cdf_resource_dumped = self._as_write_raw(remote)

        if "properties" in local_dumped and not local_dumped["properties"]:
            # In case the local properties are set to an empty dict.
            local_dumped.pop("properties", None)

        return local_dumped == cdf_resource_dumped

    def as_write(self, view: View) -> ViewApply:
        return ViewApply.load(self._as_write_raw(view))

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

    def sort_by_dependencies(self, items: Sequence[ContainerApply]) -> list[ContainerApply]:
        container_by_id = {container.as_id(): container for container in items}
        container_dependencies = {
            container.as_id(): {
                const.require
                for const in container.constraints.values()
                if isinstance(const, RequiresConstraint) and const.require in container_by_id
            }
            for container in items
        }
        return [
            container_by_id[container_id] for container_id in TopologicalSorter(container_dependencies).static_order()
        ]

    def create(self, items: Sequence[ContainerApply]) -> ContainerList:
        return self.client.data_modeling.containers.apply(items)

    def retrieve(self, ids: SequenceNotStr[ContainerId]) -> ContainerList:
        return self.client.data_modeling.containers.retrieve(cast(Sequence, ids))

    def update(self, items: Sequence[ContainerApply]) -> ContainerList:
        return self.create(items)

    def delete(self, ids: SequenceNotStr[ContainerId]) -> list[ContainerId]:
        return self.client.data_modeling.containers.delete(cast(Sequence, ids))

    def are_equal(self, local: ContainerApply, remote: Container) -> bool:
        local_dumped = local.dump(camel_case=True)
        if "usedFor" not in local_dumped:
            # Setting used_for to "node" as it is the default value in the CDF.
            local_dumped["usedFor"] = "node"

        return local_dumped == remote.as_write().dump(camel_case=True)


class DataModelLoader(DataModelingLoader[DataModelId, DataModelApply, DataModel, DataModelApplyList, DataModelList]):
    resource_name = "data_models"

    @classmethod
    def get_id(cls, item: DataModel | DataModelApply) -> DataModelId:
        return item.as_id()

    def create(self, items: Sequence[DataModelApply]) -> DataModelList:
        return self.client.data_modeling.data_models.apply(items)

    def retrieve(self, ids: SequenceNotStr[DataModelId]) -> DataModelList:
        return self.client.data_modeling.data_models.retrieve(cast(Sequence, ids))

    def update(self, items: Sequence[DataModelApply]) -> DataModelList:
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
