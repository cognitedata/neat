from cognite.neat._data_model.models.dms import (
    DataModelRequest,
)

from ._differ import ItemDiffer
from .data_classes import (
    AddedField,
    ChangedField,
    FieldChange,
    RemovedField,
    SeverityType,
)


class DataModelDiffer(ItemDiffer[DataModelRequest]):
    def diff(self, current: DataModelRequest, new: DataModelRequest) -> list[FieldChange]:
        changes: list[FieldChange] = self._diff_name_description(current, new)
        if current.views != new.views:
            # Added views
            current_views = set(current.views or [])
            for new_view in new.views or []:
                if new_view not in current_views:
                    changes.append(
                        AddedField(
                            item_severity=SeverityType.SAFE,
                            field_path="views",
                            new_value=new_view,
                        )
                    )

            # Removed views
            new_views = set(new.views or [])
            for current_view in current.views or []:
                if current_view not in new_views:
                    changes.append(
                        RemovedField(
                            item_severity=SeverityType.BREAKING,
                            field_path="views",
                            current_value=current_view,
                        )
                    )

            if not changes:
                # If there are no added or removed views, it means the order has changed
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.SAFE,
                        field_path="views",
                        current_value=str(current.views),
                        new_value=str(new.views),
                    )
                )

        return changes
