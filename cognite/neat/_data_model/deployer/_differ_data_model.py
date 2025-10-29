from cognite.neat._data_model.models.dms import (
    DataModelRequest,
)

from ._differ import ItemDiffer
from .data_classes import (
    PrimitivePropertyChange,
    PropertyChange,
    SeverityType,
)


class DataModelDiffer(ItemDiffer[DataModelRequest]):
    def diff(self, cdf_model: DataModelRequest, desired_model: DataModelRequest) -> list[PropertyChange]:
        changes: list[PropertyChange] = self._check_name_description(cdf_model, desired_model)
        if cdf_model.views != desired_model.views:
            # Change of order is considered a change.
            existing_views = set(cdf_model.views or [])
            desired_views = set(desired_model.views or [])
            changes.append(
                PrimitivePropertyChange(
                    field_path="views",
                    item_severity=SeverityType.SAFE if existing_views <= desired_views else SeverityType.BREAKING,
                    old_value=str(cdf_model.views),
                    new_value=str(desired_model.views),
                )
            )

        return changes
