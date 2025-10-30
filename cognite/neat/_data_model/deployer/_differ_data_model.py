from cognite.neat._data_model.models.dms import (
    DataModelRequest,
)

from ._differ import ItemDiffer
from .data_classes import (
    ChangedField,
    FieldChange,
    SeverityType,
)


class DataModelDiffer(ItemDiffer[DataModelRequest]):
    def diff(self, current: DataModelRequest, new: DataModelRequest) -> list[FieldChange]:
        changes: list[FieldChange] = self._diff_name_description(current, new)
        if current.views != new.views:
            # Change of order is considered a change.
            existing_views = set(current.views or [])
            desired_views = set(new.views or [])
            changes.append(
                ChangedField(
                    field_path="views",
                    item_severity=SeverityType.SAFE if existing_views <= desired_views else SeverityType.BREAKING,
                    current_value=str(current.views),
                    new_value=str(new.views),
                )
            )

        return changes
