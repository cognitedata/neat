from cognite.neat._data_model.models.dms import SpaceRequest

from ._differ import ItemDiffer
from .data_classes import PrimitivePropertyChange, PropertyChange, SeverityType


class SpaceDiffer(ItemDiffer[SpaceRequest]):
    def diff(self, cdf_space: SpaceRequest, desired_space: SpaceRequest) -> list[PropertyChange]:
        changes: list[PropertyChange] = []

        if cdf_space.name != desired_space.name:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.SAFE,
                    field_path="name",
                    old_value=cdf_space.name,
                    new_value=desired_space.name,
                )
            )

        if cdf_space.description != desired_space.description:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.SAFE,
                    field_path="description",
                    old_value=cdf_space.description,
                    new_value=desired_space.description,
                )
            )

        return changes
