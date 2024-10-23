from collections.abc import Callable, Sequence
from graphlib import TopologicalSorter
from typing import Any, Literal, cast

from cognite.client import CogniteClient
from cognite.client.data_classes import filters
from cognite.client.data_classes._base import (
    T_CogniteResourceList,
    T_WritableCogniteResource,
    T_WriteClass,
)
from cognite.client.data_classes.data_modeling import (
    Container,
    ContainerApply,
    ContainerApplyList,
    ContainerList,
    DataModel,
    DataModelApply,
    DataModelApplyList,
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
    NodeId,
    ViewId,
)
from cognite.client.exceptions import CogniteAPIError
from cognite.client.utils.useful_types import SequenceNotStr

from ._base import T_ID, ResourceLoader, T_WritableCogniteResourceList


class DataModelingLoader(
    ResourceLoader[T_ID, T_WriteClass, T_WritableCogniteResource, T_CogniteResourceList, T_WritableCogniteResourceList]
):
    @classmethod
    def in_space(cls, item: T_WriteClass | T_WritableCogniteResource | T_ID, space: set[str]) -> bool:
        if hasattr(item, "space"):
            return item.space in space
        raise ValueError(f"Item {item} does not have a space attribute")

    def sort_by_dependencies(self, items: list[T_WriteClass]) -> list[T_WriteClass]:
        return items

    def _create_force(
        self,
        items: Sequence[T_WriteClass],
        tried_force_deploy: set[T_ID],
        create_method: Callable[[Sequence[T_WriteClass]], T_WritableCogniteResourceList],
    ) -> T_WritableCogniteResourceList:
        try:
            return create_method(items)
        except CogniteAPIError as e:
            failed_items = {failed.as_id() for failed in e.failed if hasattr(failed, "as_id")}
            to_redeploy = [
                item
                for item in items
                if item.as_id() in failed_items and item.as_id() not in tried_force_deploy  # type: ignore[attr-defined]
            ]
            if not to_redeploy:
                # Avoid infinite loop
                raise e
            ids = [item.as_id() for item in to_redeploy]  # type: ignore[attr-defined]
            tried_force_deploy.update(ids)
            self.delete(ids)
            return self._create_force(to_redeploy, tried_force_deploy, create_method)


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

    def delete(self, ids: SequenceNotStr[str] | Sequence[Space | SpaceApply]) -> list[str]:
        if all(isinstance(item, Space) for item in ids) or all(isinstance(item, SpaceApply) for item in ids):
            ids = [cast(Space | SpaceApply, item).space for item in ids]
        return self.client.data_modeling.spaces.delete(cast(SequenceNotStr[str], ids))

    def clean(self, space: str) -> None:
        """Deletes all data in a space.

        This means all nodes, edges, views, containers, and data models located in the given space.

        Args:
            client: Connected CogniteClient
            space: The space to delete.

        """
        edges = self.client.data_modeling.instances.list(
            "edge", limit=-1, filter=filters.Equals(["edge", "space"], space)
        )
        if edges:
            instances = self.client.data_modeling.instances.delete(edges=edges.as_ids())
            print(f"Deleted {len(instances.edges)} edges")
        nodes = self.client.data_modeling.instances.list(
            "node", limit=-1, filter=filters.Equals(["node", "space"], space)
        )
        node_types = {NodeId(node.type.space, node.type.external_id) for node in nodes if node.type}
        node_data = set(nodes.as_ids()) - node_types
        if node_data:
            instances = self.client.data_modeling.instances.delete(nodes=list(node_data))
            print(f"Deleted {len(instances.nodes)} nodes")
        if node_types:
            instances = self.client.data_modeling.instances.delete(nodes=list(node_types))
            print(f"Deleted {len(instances.nodes)} node types")
        views = self.client.data_modeling.views.list(limit=-1, space=space)
        if views:
            deleted_views = self.client.data_modeling.views.delete(views.as_ids())
            print(f"Deleted {len(deleted_views)} views")
        containers = self.client.data_modeling.containers.list(limit=-1, space=space)
        if containers:
            deleted_containers = self.client.data_modeling.containers.delete(containers.as_ids())
            print(f"Deleted {len(deleted_containers)} containers")
        if data_models := self.client.data_modeling.data_models.list(limit=-1, space=space):
            deleted_data_models = self.client.data_modeling.data_models.delete(data_models.as_ids())
            print(f"Deleted {len(deleted_data_models)} data models")
        deleted_space = self.client.data_modeling.spaces.delete(space)
        print(f"Deleted space {deleted_space}")


class ViewLoader(DataModelingLoader[ViewId, ViewApply, View, ViewApplyList, ViewList]):
    resource_name = "views"

    def __init__(self, client: CogniteClient, existing_handling: Literal["fail", "skip", "update", "force"] = "fail"):
        super().__init__(client)
        self.existing_handling = existing_handling
        self._cache_view_by_id: dict[ViewId, View] = {}
        self._tried_force_deploy: set[ViewId] = set()

    @classmethod
    def get_id(cls, item: View | ViewApply) -> ViewId:
        return item.as_id()

    def create(self, items: Sequence[ViewApply]) -> ViewList:
        if self.existing_handling == "force":
            return self._create_force(items, self._tried_force_deploy, self.client.data_modeling.views.apply)
        else:
            return self.client.data_modeling.views.apply(items)

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
            parents = self._retrieve_view_ancestors(view.implements or [], self._cache_view_by_id)
            for parent in parents:
                for prop_name in parent.properties.keys():
                    dumped["properties"].pop(prop_name, None)

        if "properties" in dumped and not dumped["properties"]:
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

    def retrieve_all_parents(self, views: list[ViewId]) -> list[View]:
        return self._retrieve_view_ancestors(views, self._cache_view_by_id)

    def _retrieve_view_ancestors(self, parents: list[ViewId], cache: dict[ViewId, View]) -> list[View]:
        """Retrieves all ancestors of a view.

        This will mutate the cache passed in, and return a list of views that are the ancestors
        of the views in the parents list.

        Args:
            parents: The parents of the view to retrieve all ancestors for
            cache: The cache to store the views in
        """
        parent_ids = parents.copy()
        found: list[View] = []
        found_ids: set[ViewId] = set()
        while parent_ids:
            to_lookup: set[ViewId] = set()
            grand_parent_ids = []
            for parent in parent_ids:
                if parent in found_ids:
                    continue
                elif parent in cache:
                    found.append(cache[parent])
                    grand_parent_ids.extend(cache[parent].implements or [])
                else:
                    to_lookup.add(parent)

            if to_lookup:
                looked_up = self.client.data_modeling.views.retrieve(list(to_lookup))
                cache.update({view.as_id(): view for view in looked_up})
                found.extend(looked_up)
                found_ids.update({view.as_id() for view in looked_up})
                for view in looked_up:
                    grand_parent_ids.extend(view.implements or [])

            parent_ids = grand_parent_ids
        return found


class ContainerLoader(DataModelingLoader[ContainerId, ContainerApply, Container, ContainerApplyList, ContainerList]):
    resource_name = "containers"

    def __init__(self, client: CogniteClient, existing_handling: Literal["fail", "skip", "update", "force"] = "fail"):
        super().__init__(client)
        self.existing_handling = existing_handling
        self._tried_force_deploy: set[ContainerId] = set()

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
        if self.existing_handling == "force":
            return self._create_force(items, self._tried_force_deploy, self.client.data_modeling.containers.apply)
        else:
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
