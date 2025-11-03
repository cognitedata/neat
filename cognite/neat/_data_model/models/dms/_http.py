from typing import TypeAlias, TypeVar

from cognite.neat._utils.http_client import ItemBody
from cognite.neat._utils.useful_types import ReferenceObject

from ._container import ContainerRequest
from ._data_model import DataModelRequest
from ._references import (
    ContainerReference,
    DataModelReference,
    SpaceReference,
    ViewReference,
)
from ._space import SpaceRequest
from ._views import ViewRequest

DataModelResource: TypeAlias = SpaceRequest | DataModelRequest | ViewRequest | ContainerRequest

T_DataModelResource = TypeVar("T_DataModelResource", bound=DataModelResource)

ResourceId: TypeAlias = SpaceReference | DataModelReference | ViewReference | ContainerReference

T_ResourceId = TypeVar("T_ResourceId", bound=ResourceId)


class DataModelBody(ItemBody[ReferenceObject, DataModelResource]):
    def as_ids(self) -> list[ReferenceObject]:
        return [item.as_reference() for item in self.items]
