from abc import ABC, abstractmethod
from typing import Generic

from cognite.neat._utils.useful_types import T_Item

from .data_classes import PropertyChange


class ItemDiffer(Generic[T_Item], ABC):
    """A generic class for comparing two items of the same type and reporting the differences."""

    @abstractmethod
    def diff(self, cdf_resource: T_Item, desired_resource: T_Item) -> list[PropertyChange]:
        """Compare two items and return a list of changes.

        Args:
            cdf_resource: The resource as it is in CDF.
            desired_resource: The resource as it is desired to be.

        Returns:
            A list of changes between the two resources.
        """
        raise NotImplementedError()
