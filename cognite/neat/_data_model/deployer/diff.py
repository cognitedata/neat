from abc import ABC, abstractmethod
from typing import Generic

from .data_classes import PropertyChange, T_Resource


class ResourceDiffer(Generic[T_Resource], ABC):
    @abstractmethod
    def diff(self, cdf_resource: T_Resource, desired_resource: T_Resource) -> list[PropertyChange]:
        raise NotImplementedError()
