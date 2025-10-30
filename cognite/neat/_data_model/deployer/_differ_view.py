from cognite.neat._data_model.models.dms import (
    ViewPropertyDefinition,
    ViewRequest,
)
from cognite.neat._data_model.models.dms._view_property import (
    EdgeProperty,
    ReverseDirectRelationProperty,
    ViewCoreProperty,
)

from ._differ import ItemDiffer, field_differences
from .data_classes import (
    ChangedField,
    FieldChange,
    SeverityType,
)


class ViewDiffer(ItemDiffer[ViewRequest]):
    def diff(self, cdf_view: ViewRequest, desired_view: ViewRequest) -> list[FieldChange]:
        changes: list[FieldChange] = self._diff_name_description(cdf_view, desired_view)

        if cdf_view.filter != desired_view.filter:
            changes.append(
                ChangedField(
                    field_path="filter",
                    item_severity=SeverityType.BREAKING,
                    new_value=str(desired_view.filter),
                    current_value=str(cdf_view.filter),
                )
            )
        if cdf_view.implements != desired_view.implements:
            # Note that order of implements list is significant
            changes.append(
                ChangedField(
                    field_path="implements",
                    item_severity=SeverityType.BREAKING,
                    new_value=str(desired_view.implements),
                    current_value=str(cdf_view.implements),
                )
            )
        changes.extend(
            # MyPy fails to recognize that ViewPropertyDefinition and
            # the union ViewRequestProperty are the same here.
            field_differences(  # type: ignore[misc]
                "properties",
                cdf_view.properties,
                desired_view.properties,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.BREAKING,
                differ=ViewPropertyDiffer(),
            )
        )

        return changes


class ViewPropertyDiffer(ItemDiffer[ViewPropertyDefinition]):
    def diff(
        self,
        current: ViewPropertyDefinition,
        new: ViewPropertyDefinition,
    ) -> list[FieldChange]:
        changes: list[FieldChange] = self._diff_name_description(current, new)
        if current.connection_type != new.connection_type:
            changes.append(
                ChangedField(
                    field_path="connectionType",
                    item_severity=SeverityType.BREAKING,
                    new_value=new.connection_type,
                    current_value=current.connection_type,
                )
            )
        elif isinstance(current, ViewCoreProperty) and isinstance(new, ViewCoreProperty):
            changes.extend(self._diff_core_property(current, new))

        elif isinstance(current, EdgeProperty) and isinstance(new, EdgeProperty):
            changes.extend(self._diff_edge_property(current, new))

        elif isinstance(current, ReverseDirectRelationProperty) and isinstance(new, ReverseDirectRelationProperty):
            changes.extend(self._diff_reverse_direct_relation_property(current, new))

        return changes

    def _diff_core_property(
        self,
        current: ViewCoreProperty,
        new: ViewCoreProperty,
    ) -> list[FieldChange]:
        changes: list[FieldChange] = []

        if current.container != new.container:
            changes.append(
                ChangedField(
                    field_path="container",
                    # Todo check container type.
                    item_severity=SeverityType.BREAKING,
                    new_value=new.container,
                    current_value=current.container,
                )
            )
        if current.container_property_identifier != new.container_property_identifier:
            changes.append(
                ChangedField(
                    field_path="containerPropertyIdentifier",
                    # Todo check container property type.
                    item_severity=SeverityType.BREAKING,
                    new_value=new.container_property_identifier,
                    current_value=current.container_property_identifier,
                )
            )
        if current.source != new.source:
            changes.append(
                ChangedField(
                    field_path="source",
                    item_severity=SeverityType.BREAKING,
                    new_value=new.source,
                    current_value=current.source,
                )
            )

        return changes

    def _diff_edge_property(
        self,
        current: EdgeProperty,
        new: EdgeProperty,
    ) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if current.source != new.source:
            changes.append(
                ChangedField(
                    field_path="source",
                    item_severity=SeverityType.BREAKING,
                    new_value=new.source,
                    current_value=current.source,
                )
            )
        if current.type != new.type:
            changes.append(
                ChangedField(
                    field_path="type",
                    item_severity=SeverityType.BREAKING,
                    new_value=new.type,
                    current_value=current.type,
                )
            )
        if current.edge_source != new.edge_source:
            changes.append(
                ChangedField(
                    field_path="edgeSource",
                    item_severity=SeverityType.BREAKING,
                    new_value=new.edge_source,
                    current_value=current.edge_source,
                )
            )
        if current.direction != new.direction:
            changes.append(
                ChangedField(
                    field_path="direction",
                    item_severity=SeverityType.BREAKING,
                    new_value=new.direction,
                    current_value=current.direction,
                )
            )
        return changes

    def _diff_reverse_direct_relation_property(
        self,
        current: ReverseDirectRelationProperty,
        new: ReverseDirectRelationProperty,
    ) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if current.source != new.source:
            changes.append(
                ChangedField(
                    field_path="source",
                    item_severity=SeverityType.BREAKING,
                    new_value=new.source,
                    current_value=current.source,
                )
            )

        if current.through != new.through:
            changes.append(
                ChangedField(
                    field_path="through",
                    item_severity=SeverityType.BREAKING,
                    new_value=new.through,
                    current_value=current.through,
                )
            )

        return changes
