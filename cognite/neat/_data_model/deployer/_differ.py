from abc import ABC, abstractmethod
from typing import Generic

from cognite.neat._data_model.models.dms import T_Item

from .data_classes import PropertyChange


class ItemDiffer(Generic[T_Item], ABC):
    @abstractmethod
    def diff(self, cdf_resource: T_Item, desired_resource: T_Item) -> list[PropertyChange]:
        raise NotImplementedError()
