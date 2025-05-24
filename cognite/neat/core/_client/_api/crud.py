from abc import abstractmethod
from collections.abc import Hashable
from types import MappingProxyType
from typing import Any, Generic, TypeVar

from cognite.client import CogniteClient
from cognite.client.data_classes._base import CogniteResourceList, T_CogniteResource, T_CogniteResourceList
from cognite.client.data_classes.data_modeling import SpaceApply, SpaceApplyList

from cognite.neat.core._client.data_classes.deploy_result import ResourceDifference

T_ID = TypeVar("T_ID", bound=Hashable)


class CrudAPI(Generic[T_ID, T_CogniteResource, T_CogniteResourceList]):
    list_cls: type[T_CogniteResourceList]  # The class of the resource list

    def __init__(self, client: CogniteClient) -> None:
        self._client = client

    @classmethod
    def get_crud_api_cls(cls, list_cls: type[T_CogniteResourceList]) -> "type[CrudAPI]":
        """Load the appropriate CrudAPI class based on the list_cls."""
        if list_cls not in _CRUDAPI_CLASS_BY_LIST_TYPE:
            raise ValueError(f"The {list_cls.__name__} does not have a corresponding CrudAPI class.")
        return _CRUDAPI_CLASS_BY_LIST_TYPE[list_cls]

    @abstractmethod
    def create(self, resources: T_CogniteResourceList) -> T_CogniteResourceList:
        """Create a resource or a list of resources."""
        raise NotImplementedError("This method should be implemented in a subclass.")

    @abstractmethod
    def retrieve(self, ids: list[T_ID]) -> T_CogniteResourceList:
        """Retrieve a single resource by its ID."""
        raise NotImplementedError("This method should be implemented in a subclass.")

    @abstractmethod
    def update(self, resources: T_CogniteResourceList) -> T_CogniteResourceList:
        """Update a resource by its ID."""
        raise NotImplementedError("This method should be implemented in a subclass.")

    @abstractmethod
    def delete(self, ids: list[T_ID]) -> list[T_ID]:
        """Delete a resource by its ID."""
        raise NotImplementedError("This method should be implemented in a subclass.")

    @abstractmethod
    def diffs(self, cdf_resources: T_CogniteResource, local_resources: T_CogniteResource) -> Any:
        """Compare CDF resources with local resources and return the differences."""
        raise NotImplementedError("This method should be implemented in a subclass.")

    @abstractmethod
    def as_id(self, resource: T_CogniteResource) -> T_ID:
        raise NotImplementedError

    def as_ids(self, resources: T_CogniteResourceList) -> list[T_ID]:
        """Extract IDs from a resource or a list of resources."""
        return [self.as_id(resource) for resource in resources]


class SpaceCrudAPI(CrudAPI[str, SpaceApply, SpaceApplyList]):
    """CRUD API for SpaceApply resources."""

    list_cls = SpaceApplyList

    def create(self, resources: SpaceApplyList) -> SpaceApplyList:
        """Create a space or a list of spaces."""
        return self._client.data_modeling.spaces.apply(resources).as_write()

    def retrieve(self, ids: list[str]) -> SpaceApplyList:
        """Retrieve spaces by their IDs."""
        return self._client.data_modeling.spaces.retrieve(ids).as_write()

    def update(self, resources: SpaceApplyList) -> SpaceApplyList:
        """Update spaces."""
        return self._client.data_modeling.spaces.apply(resources).as_write()

    def delete(self, ids: list[str]) -> list[str]:
        """Delete spaces by their IDs."""
        return self._client.data_modeling.spaces.delete(ids)

    def as_id(self, resource: SpaceApply) -> str:
        """Extract IDs from a SpaceApplyList."""
        return resource.as_id()

    def diffs(self, cdf_resources: SpaceApply, local_resources: SpaceApply) -> ResourceDifference:
        """Compare CDF resources with local resources and return the differences."""
        raise NotImplementedError()


_CRUDAPI_CLASS_BY_LIST_TYPE: MappingProxyType[type[CogniteResourceList], type[CrudAPI]] = MappingProxyType(
    {crud.list_cls: crud for crud in CrudAPI.__subclasses__()}  # type: ignore[type-abstract, misc]
)
