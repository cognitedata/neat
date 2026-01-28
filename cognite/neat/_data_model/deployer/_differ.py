from abc import ABC, abstractmethod
from typing import Generic

from cognite.neat._utils.useful_types import T_Item

from .data_classes import (
    AddedField,
    ChangedField,
    FieldChange,
    FieldChanges,
    RemovedField,
    SeverityType,
)


class Differ(Generic[T_Item], ABC):
    def __init__(self, parent_path: str | None = None) -> None:
        self.parent_path = parent_path

    def _get_path(self, field: str) -> str:
        if self.parent_path:
            return f"{self.parent_path}.{field}"
        return field

    def _diff_name_description(self, current: T_Item, new: T_Item, identifier: str | None = None) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if hasattr(current, "name") and hasattr(new, "name"):
            if current.name != new.name:
                field_path = self._get_path(f"{identifier}.name" if identifier else "name")
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.SAFE,
                        field_path=field_path,
                        current_value=current.name,
                        new_value=new.name,
                    )
                )
        if hasattr(current, "description") and hasattr(new, "description"):
            if current.description != new.description:
                field_path = self._get_path(f"{identifier}.description" if identifier else "description")
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.SAFE,
                        field_path=field_path,
                        current_value=current.description,
                        new_value=new.description,
                    )
                )
        return changes


class ItemDiffer(Differ[T_Item], ABC):
    """A generic class for comparing two items of the same type and reporting the differences."""

    @abstractmethod
    def diff(self, current: T_Item, new: T_Item) -> list[FieldChange]:
        """Compare two items and return a list of changes.

        Args:
            current: The resource as it is in CDF.
            new: The resource as it is desired to be.

        Returns:
            A list of changes between the two resources.
        """
        raise NotImplementedError()


class ObjectDiffer(Differ[T_Item], ABC):
    @abstractmethod
    def diff(self, current: T_Item, new: T_Item, identifier: str) -> list[FieldChange]:
        """Compare two dict-like objects and return a list of changes.

        Args:
            current: The resource as it is in CDF.
            new: The resource as it is desired to be.
            identifier: The field used to identify individual items within the objects.

        Returns:
            A list of changes between the two resources.
        """
        raise NotImplementedError()


def field_differences(
    parent_path: str,
    current: dict[str, T_Item] | None,
    new: dict[str, T_Item] | None,
    add_severity: SeverityType,
    remove_severity: SeverityType,
    differ: ObjectDiffer[T_Item],
) -> list[FieldChange]:
    """Diff two containers of items.

    A container is for example the properties, constraints, or indexes of a container,
    properties of a space, views of a data model, etc.

    Args:
        parent_path: The JSON path to the container being compared.
        current: The items as they are in CDF.
        new: The items as they are desired to be.
        add_severity: The severity to assign to added items.
        remove_severity: The severity to assign to removed items.
        differ: The differ to use for comparing individual items.

    """
    changes: list[FieldChange] = []
    current_map = current or {}
    new_map = new or {}
    current_keys = set(current_map.keys())
    new_keys = set(new_map.keys())

    for key in sorted(new_keys - current_keys):
        item_path = f"{parent_path}.{key}"
        changes.append(
            AddedField(
                item_severity=add_severity,
                field_path=item_path,
                new_value=new_map[key],
            )
        )

    for key in sorted(current_keys - new_keys):
        changes.append(
            RemovedField(
                item_severity=remove_severity,
                field_path=f"{parent_path}.{key}",
                current_value=current_map[key],
            )
        )

    for key in sorted(current_keys & new_keys):
        item_path = f"{parent_path}.{key}"
        cdf_item = current_map[key]
        desired_item = new_map[key]
        diffs = differ.diff(cdf_item, desired_item, identifier=key)
        if diffs:
            changes.append(FieldChanges(field_path=item_path, changes=diffs))

    return changes
