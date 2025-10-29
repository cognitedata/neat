from cognite.neat._data_model.models.dms import (
    ViewPropertyDefinition,
    ViewRequest,
)
from cognite.neat._data_model.models.dms._view_property import (
    EdgeProperty,
    ReverseDirectRelationProperty,
    ViewCoreProperty,
)

from ._differ import ItemDiffer, diff_container
from .data_classes import (
    PrimitivePropertyChange,
    PropertyChange,
    SeverityType,
)


class ViewDiffer(ItemDiffer[ViewRequest]):
    def diff(self, cdf_view: ViewRequest, desired_view: ViewRequest) -> list[PropertyChange]:
        changes: list[PropertyChange] = self._check_name_description(cdf_view, desired_view)

        if cdf_view.filter != desired_view.filter:
            changes.append(
                PrimitivePropertyChange(
                    field_path="filter",
                    item_severity=SeverityType.BREAKING,
                    new_value=str(cdf_view.filter),
                    old_value=str(desired_view.filter),
                )
            )
        if cdf_view.implements != desired_view.implements:
            # Note that order of implements list is significant
            changes.append(
                PrimitivePropertyChange(
                    field_path="implements",
                    item_severity=SeverityType.BREAKING,
                    new_value=str(cdf_view.implements),
                    old_value=str(desired_view.implements),
                )
            )
        changes.extend(
            # MyPy fails to recognize that ViewPropertyDefinition and
            # the union ViewRequestProperty are the same here.
            diff_container(  # type: ignore[misc]
                "properties.",
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
        cdf_property: ViewPropertyDefinition,
        desired_property: ViewPropertyDefinition,
    ) -> list[PropertyChange]:
        changes: list[PropertyChange] = self._check_name_description(cdf_property, desired_property)
        if cdf_property.connection_type != desired_property.connection_type:
            changes.append(
                PrimitivePropertyChange(
                    field_path="connectionType",
                    item_severity=SeverityType.BREAKING,
                    new_value=cdf_property.connection_type,
                    old_value=desired_property.connection_type,
                )
            )
        if isinstance(cdf_property, ViewCoreProperty) and isinstance(desired_property, ViewCoreProperty):
            changes.extend(self._diff_core_property(cdf_property, desired_property))

        elif isinstance(cdf_property, EdgeProperty) and isinstance(desired_property, EdgeProperty):
            changes.extend(self._diff_edge_property(cdf_property, desired_property))

        elif isinstance(cdf_property, ReverseDirectRelationProperty) and isinstance(
            desired_property, ReverseDirectRelationProperty
        ):
            changes.extend(self._diff_reverse_direct_relation_property(cdf_property, desired_property))

        return changes

    def _diff_core_property(
        self,
        cdf_property: ViewCoreProperty,
        desired_property: ViewCoreProperty,
    ) -> list[PropertyChange]:
        changes: list[PropertyChange] = []

        if cdf_property.container != desired_property.container:
            changes.append(
                PrimitivePropertyChange(
                    field_path="container",
                    # Todo check container type.
                    item_severity=SeverityType.BREAKING,
                    new_value=cdf_property.container,
                    old_value=desired_property.container,
                )
            )
        if cdf_property.container_property_identifier != desired_property.container_property_identifier:
            changes.append(
                PrimitivePropertyChange(
                    field_path="containerPropertyIdentifier",
                    # Todo check container property type.
                    item_severity=SeverityType.BREAKING,
                    new_value=cdf_property.container_property_identifier,
                    old_value=desired_property.container_property_identifier,
                )
            )
        if cdf_property.source != desired_property.source:
            changes.append(
                PrimitivePropertyChange(
                    field_path="source",
                    item_severity=SeverityType.BREAKING,
                    new_value=cdf_property.source,
                    old_value=desired_property.source,
                )
            )

        return changes

    def _diff_edge_property(
        self,
        cdf_edge: EdgeProperty,
        desired_edge: EdgeProperty,
    ) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        if cdf_edge.source != desired_edge.source:
            changes.append(
                PrimitivePropertyChange(
                    field_path="source",
                    item_severity=SeverityType.BREAKING,
                    new_value=cdf_edge.source,
                    old_value=desired_edge.source,
                )
            )
        if cdf_edge.type != desired_edge.type:
            changes.append(
                PrimitivePropertyChange(
                    field_path="type",
                    item_severity=SeverityType.BREAKING,
                    new_value=cdf_edge.type,
                    old_value=desired_edge.type,
                )
            )
        if cdf_edge.edge_source != desired_edge.edge_source:
            changes.append(
                PrimitivePropertyChange(
                    field_path="edgeSource",
                    item_severity=SeverityType.BREAKING,
                    new_value=cdf_edge.edge_source,
                    old_value=desired_edge.edge_source,
                )
            )
        if cdf_edge.direction != desired_edge.direction:
            changes.append(
                PrimitivePropertyChange(
                    field_path="direction",
                    item_severity=SeverityType.BREAKING,
                    new_value=cdf_edge.direction,
                    old_value=desired_edge.direction,
                )
            )
        return changes

    def _diff_reverse_direct_relation_property(
        self,
        cdf_relation: ReverseDirectRelationProperty,
        desired_relation: ReverseDirectRelationProperty,
    ) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        if cdf_relation.source != desired_relation.source:
            changes.append(
                PrimitivePropertyChange(
                    field_path="source",
                    item_severity=SeverityType.BREAKING,
                    new_value=cdf_relation.source,
                    old_value=desired_relation.source,
                )
            )

        if cdf_relation.through != desired_relation.through:
            changes.append(
                PrimitivePropertyChange(
                    field_path="through",
                    item_severity=SeverityType.BREAKING,
                    new_value=cdf_relation.through,
                    old_value=desired_relation.through,
                )
            )

        return changes
