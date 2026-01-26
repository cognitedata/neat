from abc import ABC, abstractmethod
from typing import Generic

from cognite.neat._utils.useful_types import T_Item

from .data_classes import (
    AddedConstraint,
    AddedField,
    AddedIndex,
    ChangedField,
    FieldChange,
    FieldChanges,
    RemovedConstraint,
    RemovedField,
    RemovedIndex,
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
    differ: ObjectDiffer[T_Item],
    add_cls: type[AddedField] = AddedField,
    remove_cls: type[RemovedField] = RemovedField,
) -> list[FieldChange]:
    """Diff two containers of items.

    A container is for example the properties, constraints, or indexes of a container,
    properties of a space, views of a data model, etc.

    Severities are determined by the add_cls and remove_cls classes:
    - AddedField defaults to SAFE
    - RemovedField defaults to BREAKING
    - Specialized classes (e.g., AddedConstraint, RemovedIndex) override severity via property.

    Args:
        parent_path: The JSON path to the container being compared.
        current: The items as they are in CDF.
        new: The items as they are desired to be.
        differ: The differ to use for comparing individual items.
        add_cls: The class to use for added items. Defaults to AddedField (SAFE).
        remove_cls: The class to use for removed items. Defaults to RemovedField (BREAKING).

    """
    changes: list[FieldChange] = []
    current_map = current or {}
    new_map = new or {}
    current_keys = set(current_map.keys())
    new_keys = set(new_map.keys())

    for key in sorted(new_keys - current_keys):
        item_path = f"{parent_path}.{key}"
        changes.append(
            add_cls(
                field_path=item_path,
                new_value=new_map[key],
            )
        )

    for key in sorted(current_keys - new_keys):
        changes.append(
            remove_cls(
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


def constraint_differences(
    current: dict[str, T_Item] | None,
    new: dict[str, T_Item] | None,
    differ: ObjectDiffer[T_Item],
) -> list[FieldChange]:
    """Diff constraints using AddedConstraint and RemovedConstraint classes.

    Severities are fixed:
    - AddedConstraint: WARNING
    - RemovedConstraint: WARNING

    Args:
        current: The constraints as they are in CDF.
        new: The constraints as they are desired to be.
        differ: The differ to use for comparing individual constraints.
    """
    return field_differences(
        parent_path="constraints",
        current=current,
        new=new,
        differ=differ,
        add_cls=AddedConstraint,
        remove_cls=RemovedConstraint,
    )


def index_differences(
    current: dict[str, T_Item] | None,
    new: dict[str, T_Item] | None,
    differ: ObjectDiffer[T_Item],
) -> list[FieldChange]:
    """Diff indexes using AddedIndex and RemovedIndex classes.

    Severities are fixed:
    - AddedIndex: SAFE
    - RemovedIndex: WARNING

    Args:
        current: The indexes as they are in CDF.
        new: The indexes as they are desired to be.
        differ: The differ to use for comparing individual indexes.
    """
    return field_differences(
        parent_path="indexes",
        current=current,
        new=new,
        differ=differ,
        add_cls=AddedIndex,
        remove_cls=RemovedIndex,
    )
