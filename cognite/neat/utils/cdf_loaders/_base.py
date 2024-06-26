from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Generic, TypeVar

from cognite.client import CogniteClient
from cognite.client.data_classes._base import (
    T_CogniteResourceList,
    T_WritableCogniteResource,
    T_WriteClass,
    WriteableCogniteResourceList,
)
from cognite.client.utils.useful_types import SequenceNotStr

from cognite.neat._shared import T_ID

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
