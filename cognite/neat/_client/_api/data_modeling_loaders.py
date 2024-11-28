import warnings
from abc import ABC, abstractmethod
from collections.abc import Sequence
from graphlib import TopologicalSorter
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar, cast

from cognite.client.data_classes import filters
from cognite.client.data_classes._base import (
    CogniteResourceList,
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
    DataModelList,
    EdgeConnection,
    MappedProperty,
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
from cognite.client.data_classes.data_modeling.views import (
    EdgeConnectionApply,
    MappedPropertyApply,
    ReverseDirectRelation,
    ReverseDirectRelationApply,
)
from cognite.client.exceptions import CogniteAPIError
from cognite.client.utils.useful_types import SequenceNotStr

from cognite.neat._issues.warnings import CDFMaxIterationsWarning
from cognite.neat._shared import T_ID

if TYPE_CHECKING:
    from cognite.neat._client._api_client import NeatClient

T_WritableCogniteResourceList = TypeVar("T_WritableCogniteResourceList", bound=WriteableCogniteResourceList)


class ResourceLoader(
    ABC,
    Generic[T_ID, T_WriteClass, T_WritableCogniteResource, T_CogniteResourceList, T_WritableCogniteResourceList],
):
    """A resource loaders is a wrapper around the Cognite SDK that does a few things:

    * Standardizes the CRUD operations for a given resource.
    * Caches the items that have been retrieved from the CDF.
    """

    resource_name: str

    def __init__(self, client: "NeatClient") -> None:
        # This is exposed to allow for disabling the cache.
        self.cache = True
        self._client = client
        # This cache is used to store the items that have been retrieved from the CDF.
        self._items_by_id: dict[T_ID, T_WritableCogniteResource] = {}

    def bust_cache(self) -> None:
        self._items_by_id = {}

    @classmethod
    @abstractmethod
    def get_id(cls, item: T_WriteClass | T_WritableCogniteResource | dict | T_ID) -> T_ID:
        raise NotImplementedError

    @classmethod
    def get_ids(cls, items: Sequence[T_WriteClass | T_WritableCogniteResource]) -> list[T_ID]:
        return [cls.get_id(item) for item in items]

    def create(self, items: Sequence[T_WriteClass]) -> T_WritableCogniteResourceList:
        created = self._create(items)
        if self.cache:
            self._items_by_id.update({self.get_id(item): item for item in created})
        return created

    def retrieve(self, ids: SequenceNotStr[T_ID]) -> T_WritableCogniteResourceList:
        if not self.cache:
            return self._retrieve(ids)
        missing_ids = [id for id in ids if id not in self._items_by_id.keys()]
        if missing_ids:
            retrieved = self._retrieve(missing_ids)
            self._items_by_id.update({self.get_id(item): item for item in retrieved})
        # We need to check the cache again, in case we didn't retrieve all the items.
        return self._create_list([self._items_by_id[id] for id in ids if id in self._items_by_id])

    def update(self, items: Sequence[T_WriteClass]) -> T_WritableCogniteResourceList:
        if not self.cache:
            return self._update(items)
        updated = self._update(items)
        self._items_by_id.update({self.get_id(item): item for item in updated})
        return updated

    def delete(self, ids: SequenceNotStr[T_ID] | Sequence[T_WriteClass]) -> list[T_ID]:
        id_list = [self.get_id(item) for item in ids]
        if not self.cache:
            return self._delete(id_list)
        ids = [self.get_id(item) for item in ids]
        deleted = self._delete(id_list)
        for id in deleted:
            self._items_by_id.pop(id, None)
        return deleted

    @abstractmethod
    def _create(self, items: Sequence[T_WriteClass]) -> T_WritableCogniteResourceList:
        raise NotImplementedError

    @abstractmethod
    def _retrieve(self, ids: SequenceNotStr[T_ID]) -> T_WritableCogniteResourceList:
        raise NotImplementedError

    @abstractmethod
    def _update(self, items: Sequence[T_WriteClass]) -> T_WritableCogniteResourceList:
        raise NotImplementedError

    @abstractmethod
    def _delete(self, ids: SequenceNotStr[T_ID]) -> list[T_ID]:
        raise NotImplementedError

    @abstractmethod
    def _create_list(self, items: Sequence[T_WritableCogniteResource]) -> T_WritableCogniteResourceList:
        raise NotImplementedError

    def are_equal(self, local: T_WriteClass, remote: T_WritableCogniteResource) -> bool:
        return local == remote.as_write()


class DataModelingLoader(
    ResourceLoader[T_ID, T_WriteClass, T_WritableCogniteResource, T_CogniteResourceList, T_WritableCogniteResourceList],
    ABC,
):
    @classmethod
    def in_space(cls, item: T_WriteClass | T_WritableCogniteResource | T_ID, space: set[str]) -> bool:
        if hasattr(item, "space"):
            return item.space in space
        raise ValueError(f"Item {item} does not have a space attribute")

    def sort_by_dependencies(self, items: list[T_WriteClass]) -> list[T_WriteClass]:
        return items

    def create(
        self, items: Sequence[T_WriteClass], existing_handling: Literal["fail", "skip", "update", "force"] = "fail"
    ) -> T_WritableCogniteResourceList:
        if existing_handling != "force":
            return super().create(items)

        created = self._create_force(items, set())
        if self.cache:
            self._items_by_id.update({self.get_id(item): item for item in created})
        return created

    def _create_force(
        self,
        items: Sequence[T_WriteClass],
        tried_force_deploy: set[T_ID],
    ) -> T_WritableCogniteResourceList:
        try:
            return self._create(items)
        except CogniteAPIError as e:
            failed_ids = {self.get_id(failed) for failed in e.failed}
            to_redeploy = [
                item
                for item in items
                if self.get_id(item) in failed_ids and self.get_id(item) not in tried_force_deploy
            ]
            if not to_redeploy:
                # Avoid infinite loop
                raise e
            tried_force_deploy.update([self.get_id(item) for item in to_redeploy])
            self.delete(to_redeploy)
            return self._create_force(to_redeploy, tried_force_deploy)


class SpaceLoader(DataModelingLoader[str, SpaceApply, Space, SpaceApplyList, SpaceList]):
    resource_name = "spaces"

    @classmethod
    def get_id(cls, item: Space | SpaceApply | str | dict) -> str:
        if isinstance(item, Space | SpaceApply):
            return item.space
        if isinstance(item, dict):
            return item["space"]
        return item

    def _create(self, items: Sequence[SpaceApply]) -> SpaceList:
        return self._client.data_modeling.spaces.apply(items)

    def _retrieve(self, ids: SequenceNotStr[str]) -> SpaceList:
        return self._client.data_modeling.spaces.retrieve(ids)

    def _update(self, items: Sequence[SpaceApply]) -> SpaceList:
        return self._create(items)

    def _delete(self, ids: SequenceNotStr[str] | Sequence[Space | SpaceApply]) -> list[str]:
        if all(isinstance(item, Space) for item in ids) or all(isinstance(item, SpaceApply) for item in ids):
            ids = [cast(Space | SpaceApply, item).space for item in ids]
        return self._client.data_modeling.spaces.delete(cast(SequenceNotStr[str], ids))

    def _create_list(self, items: Sequence[Space]) -> SpaceList:
        return SpaceList(items)

    def clean(self, space: str) -> None:
        """Deletes all data in a space.

        This means all nodes, edges, views, containers, and data models located in the given space.

        Args:
            client: Connected CogniteClient
            space: The space to delete.

        """
        edges = self._client.data_modeling.instances.list(
            "edge", limit=-1, filter=filters.Equals(["edge", "space"], space)
        )
        if edges:
            instances = self._client.data_modeling.instances.delete(edges=edges.as_ids())
            print(f"Deleted {len(instances.edges)} edges")
        nodes = self._client.data_modeling.instances.list(
            "node", limit=-1, filter=filters.Equals(["node", "space"], space)
        )
        node_types = {NodeId(node.type.space, node.type.external_id) for node in nodes if node.type}
        node_data = set(nodes.as_ids()) - node_types
        if node_data:
            instances = self._client.data_modeling.instances.delete(nodes=list(node_data))
            print(f"Deleted {len(instances.nodes)} nodes")
        if node_types:
            instances = self._client.data_modeling.instances.delete(nodes=list(node_types))
            print(f"Deleted {len(instances.nodes)} node types")
        views = self._client.data_modeling.views.list(limit=-1, space=space)
        if views:
            deleted_views = self._client.data_modeling.views.delete(views.as_ids())
            print(f"Deleted {len(deleted_views)} views")
        containers = self._client.data_modeling.containers.list(limit=-1, space=space)
        if containers:
            deleted_containers = self._client.data_modeling.containers.delete(containers.as_ids())
            print(f"Deleted {len(deleted_containers)} containers")
        if data_models := self._client.data_modeling.data_models.list(limit=-1, space=space):
            deleted_data_models = self._client.data_modeling.data_models.delete(data_models.as_ids())
            print(f"Deleted {len(deleted_data_models)} data models")
        deleted_space = self._client.data_modeling.spaces.delete(space)
        print(f"Deleted space {deleted_space}")


class ViewLoader(DataModelingLoader[ViewId, ViewApply, View, ViewApplyList, ViewList]):
    resource_name = "views"

    @classmethod
    def get_id(cls, item: View | ViewApply | ViewId | dict) -> ViewId:
        if isinstance(item, View | ViewApply):
            return item.as_id()
        if isinstance(item, dict):
            return ViewId.load(item)
        return item

    def _create(self, items: Sequence[ViewApply]) -> ViewList:
        return self._client.data_modeling.views.apply(items)

    def retrieve(
        self, ids: SequenceNotStr[ViewId], include_connected: bool = False, include_ancestor: bool = False
    ) -> ViewList:
        if not include_connected and not include_ancestor:
            return super().retrieve(ids)
        # Retrieve recursively updates the cache.
        return self._retrieve_recursive(ids, include_connected, include_ancestor)

    def _retrieve(self, ids: SequenceNotStr[ViewId]) -> ViewList:
        return self._client.data_modeling.views.retrieve(cast(Sequence, ids))

    def _update(self, items: Sequence[ViewApply]) -> ViewList:
        return self._create(items)

    def _delete(self, ids: SequenceNotStr[ViewId]) -> list[ViewId]:
        return self._client.data_modeling.views.delete(cast(Sequence, ids))

    def _as_write_raw(self, view: View) -> dict[str, Any]:
        dumped = view.as_write().dump()
        if view.properties:
            # All read version of views have all the properties of their parent views.
            # We need to remove these properties to compare with the local view.
            parents = self._retrieve_recursive(view.implements or [], include_connections=False, include_ancestors=True)
            for parent in parents:
                for prop_name, prop in (parent.as_write().properties or {}).items():
                    existing = dumped["properties"].get(prop_name)
                    if existing is None:
                        continue
                    if existing == prop.dump():
                        dumped["properties"].pop(prop_name, None)
                    # If the child overrides the parent, we keep the child's property.

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

    def _retrieve_recursive(
        self, view_ids: SequenceNotStr[ViewId], include_connections: bool, include_ancestors: bool
    ) -> ViewList:
        """Retrieves all views with the

        This will mutate the cache passed in, and return a list of views that are the ancestors
        of the views in the parents list.

        Args:
            view_ids: The views to retrieve.
            include_connections: Whether to include all connected views.
            include_ancestors: Whether to include all ancestors.
        """
        last_batch = list(view_ids)
        found = ViewList([])
        found_ids: set[ViewId] = set()
        while last_batch:
            to_retrieve_from_cdf: set[ViewId] = set()
            batch_ids: list[ViewId] = []
            for view_id in last_batch:
                if view_id in found_ids:
                    continue
                elif view_id in self._items_by_id:
                    view = self._items_by_id[view_id]
                    found.append(view)
                    batch_ids.extend(self.get_connected_views(view, include_ancestors, include_connections, found_ids))
                else:
                    to_retrieve_from_cdf.add(view_id)

            if to_retrieve_from_cdf:
                retrieved_batch = self._client.data_modeling.views.retrieve(list(to_retrieve_from_cdf))
                self._items_by_id.update({view.as_id(): view for view in retrieved_batch})
                found.extend(retrieved_batch)
                found_ids.update({view.as_id() for view in retrieved_batch})
                for view in retrieved_batch:
                    batch_ids.extend(self.get_connected_views(view, include_ancestors, include_connections, found_ids))

            last_batch = batch_ids

        if self.cache is False:
            # We must update the cache to retrieve recursively.
            # If the cache is disabled, bust the cache to avoid storing the retrieved views.
            self.bust_cache()
        return found

    @staticmethod
    def get_connected_views(
        view: View | ViewApply,
        include_parents: bool = True,
        include_connections: bool = True,
        skip_ids: set[ViewId] | None = None,
    ) -> list[ViewId]:
        connected_ids: set[ViewId] = set(view.implements or []) if include_parents else set()
        if include_connections:
            for prop in (view.properties or {}).values():
                if isinstance(prop, MappedProperty | MappedPropertyApply) and prop.source:
                    connected_ids.add(prop.source)
                elif isinstance(
                    prop, EdgeConnection | EdgeConnectionApply | ReverseDirectRelation | ReverseDirectRelationApply
                ):
                    connected_ids.add(prop.source)

                if isinstance(prop, EdgeConnection | EdgeConnectionApply) and prop.edge_source:
                    connected_ids.add(prop.edge_source)
                elif isinstance(prop, ReverseDirectRelation | ReverseDirectRelationApply) and isinstance(
                    prop.through.source, ViewId
                ):
                    connected_ids.add(prop.through.source)
        if skip_ids:
            return [view_id for view_id in connected_ids if view_id not in skip_ids]
        return list(connected_ids)

    def _create_list(self, items: Sequence[View]) -> ViewList:
        return ViewList(items)


class ContainerLoader(DataModelingLoader[ContainerId, ContainerApply, Container, ContainerApplyList, ContainerList]):
    resource_name = "containers"

    @classmethod
    def get_id(cls, item: Container | ContainerApply | ContainerId | dict) -> ContainerId:
        if isinstance(item, Container | ContainerApply):
            return item.as_id()
        if isinstance(item, dict):
            return ContainerId.load(item)
        return item

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

    def _create(self, items: Sequence[ContainerApply]) -> ContainerList:
        return self._client.data_modeling.containers.apply(items)

    def retrieve(self, ids: SequenceNotStr[ContainerId], include_connected: bool = False) -> ContainerList:
        if not include_connected:
            return super().retrieve(ids)
        # Retrieve recursively updates the cache.
        return self._retrieve_recursive(ids)

    def _retrieve(self, ids: SequenceNotStr[ContainerId]) -> ContainerList:
        return self._client.data_modeling.containers.retrieve(cast(Sequence, ids))

    def _update(self, items: Sequence[ContainerApply]) -> ContainerList:
        return self._create(items)

    def _delete(self, ids: SequenceNotStr[ContainerId]) -> list[ContainerId]:
        return self._client.data_modeling.containers.delete(cast(Sequence, ids))

    def _create_list(self, items: Sequence[Container]) -> ContainerList:
        return ContainerList(items)

    def _retrieve_recursive(self, container_ids: SequenceNotStr[ContainerId]) -> ContainerList:
        """Containers can reference each other through the 'requires' constraint.

        This method retrieves all containers that are referenced by other containers through the 'requires' constraint,
        including their parents.
        """
        max_iterations = 10  # Limiting the number of iterations to avoid infinite loops
        found = ContainerList([])
        found_ids: set[ContainerId] = set()
        last_batch = list(container_ids)
        for _ in range(max_iterations):
            if not last_batch:
                break
            to_retrieve_from_cdf: set[ContainerId] = set()
            batch_ids: list[ContainerId] = []
            for container_id in last_batch:
                if container_id in found_ids:
                    continue
                elif container_id in self._items_by_id:
                    container = self._items_by_id[container_id]
                    found.append(container)
                    batch_ids.extend(self.get_connected_containers(container, found_ids))
                else:
                    to_retrieve_from_cdf.add(container_id)

            if to_retrieve_from_cdf:
                retrieved_batch = self._client.data_modeling.containers.retrieve(list(to_retrieve_from_cdf))
                self._items_by_id.update({view.as_id(): view for view in retrieved_batch})
                found.extend(retrieved_batch)
                found_ids.update({view.as_id() for view in retrieved_batch})
                for container in retrieved_batch:
                    batch_ids.extend(self.get_connected_containers(container, found_ids))

            last_batch = batch_ids
        else:
            warnings.warn(
                CDFMaxIterationsWarning(
                    "The maximum number of iterations was reached while resolving referenced containers."
                    "There might be referenced containers that are not included in the list of containers.",
                    max_iterations=max_iterations,
                ),
                stacklevel=2,
            )

        if self.cache is False:
            # We must update the cache to retrieve recursively.
            # If the cache is disabled, bust the cache to avoid storing the retrieved views.
            self.bust_cache()
        return found

    @staticmethod
    def get_connected_containers(
        container: Container | ContainerApply, skip: set[ContainerId] | None = None
    ) -> set[ContainerId]:
        connected_containers = set()
        for constraint in container.constraints.values():
            if isinstance(constraint, RequiresConstraint):
                connected_containers.add(constraint.require)
        if skip:
            return {container_id for container_id in connected_containers if container_id not in skip}
        return connected_containers

    def are_equal(self, local: ContainerApply, remote: Container) -> bool:
        local_dumped = local.dump(camel_case=True)
        if "usedFor" not in local_dumped:
            # Setting used_for to "node" as it is the default value in the CDF.
            local_dumped["usedFor"] = "node"

        return local_dumped == remote.as_write().dump(camel_case=True)


class DataModelLoader(DataModelingLoader[DataModelId, DataModelApply, DataModel, DataModelApplyList, DataModelList]):
    resource_name = "data_models"

    @classmethod
    def get_id(cls, item: DataModel | DataModelApply | DataModelId | dict) -> DataModelId:
        if isinstance(item, DataModel | DataModelApply):
            return item.as_id()
        if isinstance(item, dict):
            return DataModelId.load(item)
        return item

    def _create(self, items: Sequence[DataModelApply]) -> DataModelList:
        return self._client.data_modeling.data_models.apply(items)

    def _retrieve(self, ids: SequenceNotStr[DataModelId]) -> DataModelList:
        return self._client.data_modeling.data_models.retrieve(cast(Sequence, ids))

    def _update(self, items: Sequence[DataModelApply]) -> DataModelList:
        return self._create(items)

    def _delete(self, ids: SequenceNotStr[DataModelId]) -> list[DataModelId]:
        return self._client.data_modeling.data_models.delete(cast(Sequence, ids))

    def _create_list(self, items: Sequence[DataModel]) -> DataModelList:
        return DataModelList(items)

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


class DataModelLoaderAPI:
    def __init__(self, client: "NeatClient") -> None:
        self._client = client
        self.spaces = SpaceLoader(client)
        self.views = ViewLoader(client)
        self.containers = ContainerLoader(client)
        self.data_models = DataModelLoader(client)

    def get_loader(self, items: Any) -> DataModelingLoader:
        if isinstance(items, CogniteResourceList):
            resource_name = type(items).__name__.casefold().removesuffix("list").removesuffix("apply")
        elif isinstance(items, str):
            resource_name = items
        else:
            raise ValueError(f"Cannot determine resource name from {items}")
        if resource_name[-1] != "s":
            resource_name += "s"
        if resource_name == "datamodels":
            resource_name = "data_models"
        return getattr(self, resource_name)
