import warnings
from abc import ABC, abstractmethod
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass, field
from graphlib import TopologicalSorter
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Literal, TypeVar, cast, overload

from cognite.client.data_classes import filters
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
    DataModelList,
    EdgeConnection,
    MappedProperty,
    Node,
    NodeApply,
    NodeApplyList,
    NodeList,
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

from cognite.neat._client.data_classes.data_modeling import Component
from cognite.neat._client.data_classes.schema import DMSSchema
from cognite.neat._issues.warnings import CDFMaxIterationsWarning
from cognite.neat._shared import T_ID

if TYPE_CHECKING:
    from cognite.neat._client._api_client import NeatClient

T_WritableCogniteResourceList = TypeVar("T_WritableCogniteResourceList", bound=WriteableCogniteResourceList)

T_Item = TypeVar("T_Item")
T_Out = TypeVar("T_Out", bound=Iterable)


@dataclass
class MultiCogniteAPIError(Exception, Generic[T_ID, T_WritableCogniteResourceList]):
    success: T_WritableCogniteResourceList
    failed: list[T_ID] = field(default_factory=list)
    errors: list[CogniteAPIError] = field(default_factory=list)


class ResourceLoader(
    ABC,
    Generic[T_ID, T_WriteClass, T_WritableCogniteResource, T_CogniteResourceList, T_WritableCogniteResourceList],
):
    """A resource loaders is a wrapper around the Cognite SDK that does a few things:

    * Standardizes the CRUD operations for a given resource.
    * Caches the items that have been retrieved from the CDF.
    """

    resource_name: str
    dependencies: "ClassVar[frozenset[type[ResourceLoader]]]" = frozenset()

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
        # Containers can have dependencies on other containers, so we sort them before creating them.
        items = self.sort_by_dependencies(items)

        exception: MultiCogniteAPIError[T_ID, T_WritableCogniteResourceList] | None = None
        try:
            created = self._fallback_one_by_one(self._create, items)
        except MultiCogniteAPIError as e:
            created = e.success
            exception = e

        if self.cache:
            self._items_by_id.update({self.get_id(item): item for item in created})

        if exception is not None:
            raise exception

        return created

    @overload
    def retrieve(
        self, ids: SequenceNotStr[T_ID], format: Literal["read"] = "read"
    ) -> T_WritableCogniteResourceList: ...

    @overload
    def retrieve(self, ids: SequenceNotStr[T_ID], format: Literal["write"] = "write") -> T_CogniteResourceList: ...

    def retrieve(
        self, ids: SequenceNotStr[T_ID], format: Literal["read", "write"] = "read"
    ) -> T_WritableCogniteResourceList | T_CogniteResourceList:
        if not self.cache:
            # We now that SequenceNotStr = Sequence
            output = self._fallback_one_by_one(self._retrieve, ids)  # type: ignore[arg-type]
        else:
            exception: MultiCogniteAPIError[T_ID, T_WritableCogniteResourceList] | None = None
            missing_ids = [id for id in ids if id not in self._items_by_id.keys()]
            if missing_ids:
                try:
                    retrieved = self._retrieve(missing_ids)
                except MultiCogniteAPIError as e:
                    retrieved = e.success
                    exception = e
                self._items_by_id.update({self.get_id(item): item for item in retrieved})
            if exception is not None:
                raise exception
            # We need to check the cache again, in case we didn't retrieve all the items.
            output = self._create_list([self._items_by_id[id] for id in ids if id in self._items_by_id])
        if format == "write":
            return cast(T_CogniteResourceList, output.as_write())
        return output

    def update(
        self, items: Sequence[T_WriteClass], force: bool = False, drop_data: bool = False
    ) -> T_WritableCogniteResourceList:
        exception: MultiCogniteAPIError[T_ID, T_WritableCogniteResourceList] | None = None
        if force:
            updated = self._update_force(items, drop_data=drop_data)
        else:
            try:
                updated = self._fallback_one_by_one(self._update, items)
            except MultiCogniteAPIError as e:
                updated = e.success
                exception = e

        if self.cache:
            self._items_by_id.update({self.get_id(item): item for item in updated})

        if exception is not None:
            raise exception

        return updated

    def delete(self, ids: SequenceNotStr[T_ID] | Sequence[T_WriteClass]) -> list[T_ID]:
        id_list = [self.get_id(item) for item in ids]
        exception: MultiCogniteAPIError[T_ID, T_WritableCogniteResourceList] | None = None
        try:
            # We know that SequenceNotStr = Sequence
            deleted = self._fallback_one_by_one(self._delete, id_list)  # type: ignore[arg-type]
        except MultiCogniteAPIError as e:
            deleted = e.success
            exception = e

        if self.cache:
            for id in deleted:
                self._items_by_id.pop(id, None)
        if exception is not None:
            raise exception

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

    def has_data(self, item_id: T_ID) -> bool:
        return False

    def are_equal(self, local: T_WriteClass, remote: T_WritableCogniteResource) -> bool:
        return local == remote.as_write()

    def sort_by_dependencies(self, items: Sequence[T_WriteClass]) -> list[T_WriteClass]:
        return list(items)

    def _update_force(
        self,
        items: Sequence[T_WriteClass],
        drop_data: bool = False,
        tried_force_update: set[T_ID] | None = None,
        success: T_WritableCogniteResourceList | None = None,
    ) -> T_WritableCogniteResourceList:
        tried_force_update = tried_force_update or set()
        try:
            return self._update(items)
        except CogniteAPIError as e:
            failed_ids = {self.get_id(failed) for failed in e.failed + e.unknown}
            success_ids = [self.get_id(success) for success in e.successful]
            success_ = self.retrieve(success_ids)
            if success is None:
                success = success_
            else:
                success.extend(success_)
            to_redeploy: list[T_WriteClass] = []
            for item in items:
                item_id = self.get_id(item)
                if item_id in failed_ids:
                    if tried_force_update and item_id in tried_force_update:
                        # Avoid infinite loop
                        continue
                    tried_force_update.add(item_id)
                    if self.has_data(item_id) and not drop_data:
                        continue
                    to_redeploy.append(item)
            if not to_redeploy:
                # Avoid infinite loop
                raise e
            self.delete(to_redeploy)
            forced = self._update_force(to_redeploy, drop_data, tried_force_update, success)
            forced.extend(success)
            return forced

    def _fallback_one_by_one(self, method: Callable[[Sequence[T_Item]], T_Out], items: Sequence[T_Item]) -> T_Out:
        try:
            return method(items)
        except CogniteAPIError as e:
            exception = MultiCogniteAPIError[T_ID, T_WritableCogniteResourceList](self._create_list([]))
            success = {self.get_id(success) for success in e.successful}
            if success:
                # Need read version of the items to put into cache.
                retrieve_items = self.retrieve(list(success))
                exception.success.extend(retrieve_items)
            for item in items:
                # We know that item is either T_ID or T_WriteClass
                # but the T_Item cannot be bound to both types at the same time.
                item_id = self.get_id(item)  # type: ignore[arg-type]
                if item_id in success:
                    continue
                try:
                    item_result = method([item])
                except CogniteAPIError as item_exception:
                    exception.errors.append(item_exception)
                    exception.failed.extend(self.get_ids(item_exception.failed))
                else:
                    exception.success.extend(item_result)
            raise exception from None


class DataModelingLoader(
    ResourceLoader[T_ID, T_WriteClass, T_WritableCogniteResource, T_CogniteResourceList, T_WritableCogniteResourceList],
    ABC,
):
    support_merge: ClassVar[bool] = True

    @classmethod
    def in_space(cls, item: T_WriteClass | T_WritableCogniteResource | T_ID, space: set[str]) -> bool:
        if hasattr(item, "space"):
            return item.space in space
        raise ValueError(f"Item {item} does not have a space attribute")

    @classmethod
    @abstractmethod
    def items_from_schema(cls, schema: DMSSchema) -> T_CogniteResourceList:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def merge(cls, local: T_WriteClass, remote: T_WritableCogniteResource) -> T_WriteClass:
        raise NotImplementedError


class SpaceLoader(DataModelingLoader[str, SpaceApply, Space, SpaceApplyList, SpaceList]):
    resource_name = "spaces"
    support_merge = False

    @classmethod
    def get_id(cls, item: Space | SpaceApply | str | dict) -> str:
        if isinstance(item, Space | SpaceApply):
            return item.space
        if isinstance(item, dict):
            return item["space"]
        return item

    @classmethod
    def merge(cls, local: SpaceApply, remote: Space) -> SpaceApply:
        raise NotImplementedError("Spaces cannot be merged")

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

    @classmethod
    def items_from_schema(cls, schema: DMSSchema) -> SpaceApplyList:
        return SpaceApplyList(schema.spaces.values())

    def has_data(self, item_id: str) -> bool:
        if self._client.data_modeling.instances.list("node", limit=1, space=item_id):
            return True
        if self._client.data_modeling.instances.list("edge", limit=1, space=item_id):
            return True
        # Need to check if there are any containers with data in the space. Typically,
        # a schema space will not contain data, while it will have containers that have data in an instance space.
        for container in self._client.data_modeling.containers(space=item_id, include_global=False):
            if self._client.loaders.containers.has_data(container.as_id()):
                return True
        return False


class ContainerLoader(DataModelingLoader[ContainerId, ContainerApply, Container, ContainerApplyList, ContainerList]):
    resource_name = "containers"
    dependencies = frozenset({SpaceLoader})

    @classmethod
    def get_id(cls, item: Container | ContainerApply | ContainerId | dict) -> ContainerId:
        if isinstance(item, Container | ContainerApply):
            return item.as_id()
        if isinstance(item, dict):
            return ContainerId.load(item)
        return item

    @classmethod
    def merge(cls, local: ContainerApply, remote: Container) -> ContainerApply:
        if local.as_id() != remote.as_id():
            raise ValueError(f"Cannot merge containers with different IDs: {local.as_id()} and {remote.as_id()}")
        if local.used_for != remote.used_for:
            raise ValueError(f"Cannot merge containers with different used_for: {local.used_for} and {remote.used_for}")
        remote_write = remote.as_write()
        existing_properties = remote_write.properties or {}
        merged_properties = {**existing_properties, **(local.properties or {})}
        merged_indices = {**remote_write.indexes, **local.indexes}
        merged_constraints = {**remote_write.constraints, **local.constraints}
        return ContainerApply(
            space=remote.space,
            external_id=remote.external_id,
            properties=merged_properties,
            description=local.description or remote.description,
            name=local.name or remote.name,
            used_for=local.used_for,
            constraints=merged_constraints,
            indexes=merged_indices,
        )

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

    @overload
    def retrieve(
        self, ids: SequenceNotStr[ContainerId], format: Literal["read"] = "read", include_connected: bool = False
    ) -> ContainerList: ...

    @overload
    def retrieve(
        self, ids: SequenceNotStr[ContainerId], format: Literal["write"] = "write", include_connected: bool = False
    ) -> ContainerApplyList: ...

    def retrieve(
        self,
        ids: SequenceNotStr[ContainerId],
        format: Literal["read", "write"] = "read",
        include_connected: bool = False,
    ) -> ContainerList | ContainerApplyList:
        if not include_connected:
            return super().retrieve(ids)

        # Retrieve recursively updates the cache.
        output = self._retrieve_recursive(ids)
        if format == "write":
            return output.as_write()
        return output

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

    @classmethod
    def items_from_schema(cls, schema: DMSSchema) -> ContainerApplyList:
        return ContainerApplyList(schema.containers.values())

    def has_data(self, item_id: ContainerId) -> bool:
        has_data_filter = filters.HasData(containers=[item_id])
        has_data = False
        instance_type: Literal["node", "edge"]
        # Mypy does not understand that the instance type is Literal["node", "edge"]
        for instance_type in ["node", "edge"]:  # type: ignore[assignment]
            try:
                has_data = bool(
                    self._client.data_modeling.instances.list(instance_type, limit=1, filter=has_data_filter)
                )
            except CogniteAPIError as e:
                if e.code != 400:
                    # If the container is used for nodes and we ask for edges, we get a 400 error. This
                    # means there is no edge data for this container.
                    raise
            if has_data:
                return True
        return has_data


class ViewLoader(DataModelingLoader[ViewId, ViewApply, View, ViewApplyList, ViewList]):
    resource_name = "views"
    dependencies = frozenset({SpaceLoader, ContainerLoader})

    @classmethod
    def get_id(cls, item: View | ViewApply | ViewId | dict) -> ViewId:
        if isinstance(item, View | ViewApply):
            return item.as_id()
        if isinstance(item, dict):
            return ViewId.load(item)
        return item

    @classmethod
    def merge(cls, local: ViewApply, remote: View) -> ViewApply:
        if local.as_id() != remote.as_id():
            raise ValueError(f"Cannot merge views with different IDs: {local.as_id()} and {remote.as_id()}")
        remote_write = remote.as_write()
        existing_properties = remote_write.properties or {}
        merged_properties = {**existing_properties, **(local.properties or {})}
        merged_implements = list(remote_write.implements or [])
        for view_id in local.implements or []:
            if view_id not in merged_implements:
                merged_implements.append(view_id)
        return ViewApply(
            space=remote.space,
            external_id=remote.external_id,
            version=remote.version,
            properties=merged_properties,
            description=local.description or remote.description,
            name=local.name or remote.name,
            filter=local.filter or remote.filter,
            implements=merged_implements,
        )

    def _create(self, items: Sequence[ViewApply]) -> ViewList:
        return self._client.data_modeling.views.apply(items)

    @overload
    def retrieve(
        self,
        ids: SequenceNotStr[ViewId],
        format: Literal["read"] = "read",
        include_connected: bool = False,
        include_ancestor: bool = False,
    ) -> ViewList: ...

    @overload
    def retrieve(
        self,
        ids: SequenceNotStr[ViewId],
        format: Literal["write"] = "write",
        include_connected: bool = False,
        include_ancestor: bool = False,
    ) -> ViewApplyList: ...

    def retrieve(
        self,
        ids: SequenceNotStr[ViewId],
        format: Literal["read", "write"] = "read",
        include_connected: bool = False,
        include_ancestor: bool = False,
    ) -> ViewList | ViewApplyList:
        if not include_connected and not include_ancestor:
            # Default .as_write() method does not work for views as they include parent properties.
            output = super().retrieve(ids)
        else:
            # Retrieve recursively updates the cache.
            output = self._retrieve_recursive(ids, include_connected, include_ancestor)
        if format == "write":
            return ViewApplyList([self.as_write(view) for view in output])
        return output

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
        last_batch = set(view_ids)
        found = ViewList([])
        found_ids: set[ViewId] = set()
        while last_batch:
            to_retrieve_from_cdf: set[ViewId] = set()
            batch_ids: set[ViewId] = set()
            for view_id in last_batch:
                if view_id in found_ids:
                    continue
                elif view_id in self._items_by_id:
                    view = self._items_by_id[view_id]
                    found.append(view)
                    found_ids.add(view_id)
                    batch_ids.update(self.get_connected_views(view, include_ancestors, include_connections, found_ids))
                else:
                    to_retrieve_from_cdf.add(view_id)

            if to_retrieve_from_cdf:
                retrieved_batch = self._client.data_modeling.views.retrieve(list(to_retrieve_from_cdf))
                self._items_by_id.update({view.as_id(): view for view in retrieved_batch})
                found.extend(retrieved_batch)
                found_ids.update({view.as_id() for view in retrieved_batch})
                for view in retrieved_batch:
                    batch_ids.update(self.get_connected_views(view, include_ancestors, include_connections, found_ids))
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

    @classmethod
    def items_from_schema(cls, schema: DMSSchema) -> ViewApplyList:
        return ViewApplyList(schema.views.values())


class DataModelLoader(DataModelingLoader[DataModelId, DataModelApply, DataModel, DataModelApplyList, DataModelList]):
    resource_name = "data_models"
    dependencies = frozenset({SpaceLoader, ViewLoader})

    @classmethod
    def get_id(cls, item: DataModel | DataModelApply | DataModelId | dict) -> DataModelId:
        if isinstance(item, DataModel | DataModelApply):
            return item.as_id()
        if isinstance(item, dict):
            return DataModelId.load(item)
        return item

    @classmethod
    def merge(cls, local: DataModelApply, remote: DataModel) -> DataModelApply:
        if local.as_id() != remote.as_id():
            raise ValueError(f"Cannot merge data models with different IDs: {local.as_id()} and {remote.as_id()}")
        existing_view = {
            view.as_id() if isinstance(view, View) else view: view.as_write() if isinstance(view, View) else view
            for view in remote.views
        }
        new_views = {view.as_id() if isinstance(view, ViewApply) else view: view for view in local.views or []}
        merged_views: list[ViewId | ViewApply] = []
        for view_id, view in existing_view.items():
            if view_id in new_views:
                merged_views.append(new_views.pop(view_id))
            else:
                merged_views.append(view)
        merged_views.extend(new_views.values())

        return DataModelApply(
            space=local.space,
            external_id=local.external_id,
            version=local.version,
            description=local.description or remote.description,
            name=local.name or remote.name,
            views=merged_views,
        )

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

    @classmethod
    def items_from_schema(cls, schema: DMSSchema) -> DataModelApplyList:
        return DataModelApplyList([schema.data_model])


class NodeLoader(DataModelingLoader[NodeId, NodeApply, Node, NodeApplyList, NodeList]):
    resource_name = "nodes"
    dependencies = frozenset({SpaceLoader, ContainerLoader, ViewLoader})
    support_merge = False

    @classmethod
    def get_id(cls, item: Node | NodeApply | NodeId | dict) -> NodeId:
        if isinstance(item, Node | NodeApply):
            return item.as_id()
        if isinstance(item, dict):
            return NodeId.load(item)
        return item

    @classmethod
    def merge(cls, local: NodeApply, remote: Node) -> NodeApply:
        raise NotImplementedError("Nodes cannot be merged")

    def _create(self, items: Sequence[NodeApply]) -> NodeList:
        self._client.data_modeling.instances.apply(items)
        return self._retrieve([item.as_id() for item in items])

    def _retrieve(self, ids: SequenceNotStr[NodeId]) -> NodeList:
        return self._client.data_modeling.instances.retrieve(cast(Sequence, ids)).nodes

    def _update(self, items: Sequence[NodeApply]) -> NodeList:
        self._client.data_modeling.instances.apply(items, replace=True)
        return self._retrieve([item.as_id() for item in items])

    def _delete(self, ids: SequenceNotStr[NodeId]) -> list[NodeId]:
        return list(self._client.data_modeling.instances.delete(nodes=cast(Sequence, ids)).nodes)

    def _create_list(self, items: Sequence[Node]) -> NodeList:
        return NodeList(items)

    def are_equal(self, local: NodeApply, remote: Node) -> bool:
        local_dumped = local.dump()

        # Note reading from a container is not supported.
        sources = [
            source_prop_pair.source
            for source_prop_pair in local.sources or []
            if isinstance(source_prop_pair.source, ViewId)
        ]
        if sources:
            try:
                cdf_resource_with_properties = self._client.data_modeling.instances.retrieve(
                    nodes=remote.as_id(), sources=sources
                ).nodes[0]
            except CogniteAPIError:
                # View does not exist, so node does not exist.
                return False
        else:
            cdf_resource_with_properties = remote
        cdf_resource_dumped = cdf_resource_with_properties.as_write().dump()

        if "existingVersion" not in local_dumped:
            # Existing version is typically not set when creating nodes, but we get it back
            # when we retrieve the node from the server.
            local_dumped["existingVersion"] = cdf_resource_dumped.get("existingVersion", None)

        return local_dumped == cdf_resource_dumped

    @classmethod
    def items_from_schema(cls, schema: DMSSchema) -> NodeApplyList:
        return NodeApplyList(schema.node_types.values())


class DataModelLoaderAPI:
    def __init__(self, client: "NeatClient") -> None:
        self._client = client
        self.spaces = SpaceLoader(client)
        self.views = ViewLoader(client)
        self.containers = ContainerLoader(client)
        self.data_models = DataModelLoader(client)
        self.nodes = NodeLoader(client)
        self._loaders: list[DataModelingLoader] = [
            self.spaces,
            self.views,
            self.containers,
            self.data_models,
            self.nodes,
        ]

    def by_dependency_order(
        self, component: Component | Collection[Component] | None = None
    ) -> list[DataModelingLoader]:
        loader_by_type = {type(loader): loader for loader in self._loaders}
        loader_iterable = (
            loader_by_type[loader_cls]  # type: ignore[index]
            for loader_cls in TopologicalSorter(
                {type(loader): loader.dependencies for loader in self._loaders}  # type: ignore[attr-defined]
            ).static_order()
        )
        if component is None:
            return list(loader_iterable)
        components = {component} if isinstance(component, str) else set(component)
        components = {{"node_type": "nodes"}.get(component, component) for component in components}
        return [loader for loader in loader_iterable if loader.resource_name in components]
