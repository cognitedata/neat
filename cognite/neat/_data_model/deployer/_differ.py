from abc import ABC, abstractmethod
from typing import Generic

from cognite.neat._data_model.models.dms import T_Item

from .data_classes import (
    AddedProperty,
    ContainerPropertyChange,
    PrimitivePropertyChange,
    PropertyChange,
    RemovedProperty,
    SeverityType,
)


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

    @classmethod
    def _check_name_description(cls, cdf_item: T_Item, desired_item: T_Item) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        if hasattr(cdf_item, "name") and hasattr(desired_item, "name"):
            if cdf_item.name != desired_item.name:
                changes.append(
                    PrimitivePropertyChange(
                        item_severity=SeverityType.SAFE,
                        field_path="name",
                        old_value=cdf_item.name,
                        new_value=desired_item.name,
                    )
                )
        if hasattr(cdf_item, "description") and hasattr(desired_item, "description"):
            if cdf_item.description != desired_item.description:
                changes.append(
                    PrimitivePropertyChange(
                        item_severity=SeverityType.SAFE,
                        field_path="description",
                        old_value=cdf_item.description,
                        new_value=desired_item.description,
                    )
                )
        return changes


def diff_container(
    parent_path: str,
    cdf_items: dict[str, T_Item] | None,
    desired_items: dict[str, T_Item] | None,
    add_severity: SeverityType,
    remove_severity: SeverityType,
    differ: ItemDiffer[T_Item],
) -> list[PropertyChange]:
    """Diff two containers of items.

    A container is for example the properties, constraints, or indexes of a container,
    properties of a space, views of a data model, etc.

    Args:
        parent_path: The JSON path to the container being compared.
        cdf_items: The items as they are in CDF.
        desired_items: The items as they are desired to be.
        add_severity: The severity to assign to added items.
        remove_severity: The severity to assign to removed items.
        differ: The differ to use for comparing individual items.

    """
    changes: list[PropertyChange] = []
    for key, desired_item in (desired_items or {}).items():
        item_path = f"{parent_path}{key}"
        if cdf_items is None or key not in cdf_items:
            changes.append(
                AddedProperty(
                    item_severity=add_severity,
                    field_path=item_path,
                    new_value=desired_item,
                )
            )
            continue
        cdf_item = cdf_items[key]
        diffs = differ.diff(cdf_item, desired_item)
        if diffs:
            changes.append(ContainerPropertyChange(field_path=item_path, changed_items=diffs))

    if desired_items is not None:
        for key, cdf_item in (cdf_items or {}).items():
            if key not in desired_items:
                changes.append(
                    RemovedProperty(
                        item_severity=remove_severity,
                        field_path=f"{parent_path}{key}",
                        old_value=cdf_item,
                    )
                )
    return changes
