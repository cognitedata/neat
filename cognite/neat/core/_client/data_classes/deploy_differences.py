from collections.abc import Mapping
from typing import Literal, TypeAlias

from .deploy_result import Property, PropertyChange, ResourceDifference

Primary: TypeAlias = int | str | float | bool


class DifferenceFactory:
    @classmethod
    def nullable_primary(
        cls, difference: ResourceDifference, location: str, new: Primary | None, previous: Primary | None
    ) -> None:
        """
        Finds the difference in primary values. The difference object is modified to include nullable primary values.

        Args:
            difference (ResourceDifference): The base difference object.
            location (str): The location of the property change.
            new (Primary | None): The new primary value.
            previous (Primary | None): The previous primary value.

        Returns:
            ResourceDifference: A new ResourceDifference with nullable primary values.
        """
        if new is not None and previous is not None and new != previous:
            difference.changed.append(
                PropertyChange(location=location, value_representation=str(new), previous_representation=str(previous))
            )
        elif new is not None and previous is None:
            difference.added.append(Property(location=location, value_representation=str(new)))
        elif new is None and previous is not None:
            difference.removed.append(Property(location=location, value_representation=str(previous)))

    @classmethod
    def comparable_by_id(
        cls,
        difference: ResourceDifference,
        location: str,
        new: Mapping[str, object],
        previous: Mapping[str, object],
        existing: Literal["merge", "overwrite"] = "merge",
    ) -> None:
        """
        Finds the difference in dictionary values by ID. The difference object is
        modified to include changes in dictionaries.

        Args:
            difference (ResourceDifference): The base difference object.
            location (str): The location of the property change.
            new (dict[Primary, Primary] | None): The new dictionary value.
            previous (dict[Primary, Primary] | None): The previous dictionary value.
            existing (Literal["merge", 'overwrite']): How to handle existing keys. If "merge",
                changes are merged; if "overwrite", existing keys are replaced.

        Returns:
            ResourceDifference: A new ResourceDifference with dictionary changes.
        """
        for key in set(new.keys()).intersection(previous.keys()):
            new_value = new.get(key)
            previous_value = previous.get(key)
            if new_value != previous_value:
                difference.changed.append(PropertyChange(f"{location}.{key}"))
        for new_key in new:
            if new_key not in previous:
                difference.added.append(Property(location=f"{location}.{new_key}"))
        if existing == "overwrite":
            for previous_key in previous:
                if previous_key not in new:
                    difference.removed.append(Property(location=f"{location}.{previous_key}"))
