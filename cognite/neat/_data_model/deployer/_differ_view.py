from cognite.neat._data_model.models.dms import (
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    ViewPropertyDefinition,
    ViewRequest,
)
from cognite.neat._data_model.models.dms._view_property import (
    EdgeProperty,
    ReverseDirectRelationProperty,
    ViewCoreProperty,
    ViewCorePropertyRequest,
)

from ._differ import ItemDiffer, ObjectDiffer, field_differences
from ._differ_container import ContainerPropertyDiffer
from .data_classes import (
    AddedField,
    ChangedField,
    FieldChange,
    RemovedField,
    SeverityType,
)


class ViewDiffer(ItemDiffer[ViewRequest]):
    def __init__(
        self,
        current_container_map: dict[ContainerReference, ContainerRequest],
        new_container_map: dict[ContainerReference, ContainerRequest],
        parent_path: str | None = None,
    ):
        super().__init__(parent_path)
        self._current_container_map = current_container_map
        self._new_containe_map = new_container_map

    def diff(self, current: ViewRequest, new: ViewRequest) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if current.implements != new.implements:
            # Added implements
            current_implements = set(current.implements or [])
            for new_implements in new.implements or []:
                if new_implements not in current_implements:
                    changes.append(
                        AddedField(
                            item_severity=SeverityType.BREAKING,
                            field_path="implements",
                            new_value=new_implements,
                        )
                    )

            # Removed implements
            new_implements = set(new.implements or [])
            for current_implements in current.implements or []:
                if current_implements not in new_implements:
                    changes.append(
                        RemovedField(
                            item_severity=SeverityType.BREAKING,
                            field_path="implements",
                            current_value=current_implements,
                        )
                    )

            if not changes:
                # If there are no added or removed implements, it means the order has changed
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.SAFE,
                        field_path="implements",
                        current_value=str(current.implements),
                        new_value=str(new.implements),
                    )
                )

        changes.extend(self._diff_name_description(current, new))

        if current.filter != new.filter:
            changes.append(
                ChangedField(
                    field_path=self._get_path("filter"),
                    item_severity=SeverityType.WARNING,
                    new_value=str(new.filter),
                    current_value=str(current.filter),
                )
            )

        changes.extend(
            # MyPy fails to recognize that ViewPropertyDefinition and
            # the union ViewRequestProperty are the same here.
            field_differences(  # type: ignore[misc]
                "properties",
                current.properties,
                new.properties,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.BREAKING,
                differ=ViewPropertyDiffer(
                    self._current_container_map, self._new_containe_map, self._get_path("properties")
                ),
            )
        )

        return changes


class ViewPropertyDiffer(ObjectDiffer[ViewPropertyDefinition]):
    def __init__(
        self,
        current_container_map: dict[ContainerReference, ContainerRequest],
        new_container_map: dict[ContainerReference, ContainerRequest],
        parent_path: str | None = None,
    ):
        super().__init__(parent_path)
        self._current_container_map = current_container_map
        self._new_container_map = new_container_map

    def diff(
        self,
        current: ViewPropertyDefinition,
        new: ViewPropertyDefinition,
        identifier: str,
    ) -> list[FieldChange]:
        changes: list[FieldChange] = self._diff_name_description(current, new, identifier)
        if current.connection_type != new.connection_type:
            changes.append(
                ChangedField(
                    field_path=self._get_path(f"{identifier}.connectionType"),
                    item_severity=SeverityType.BREAKING,
                    new_value=new.connection_type,
                    current_value=current.connection_type,
                )
            )
        elif isinstance(current, ViewCoreProperty) and isinstance(new, ViewCoreProperty):
            changes.extend(self._diff_core_property(current, new, identifier))

        elif isinstance(current, EdgeProperty) and isinstance(new, EdgeProperty):
            changes.extend(self._diff_edge_property(current, new, identifier))

        elif isinstance(current, ReverseDirectRelationProperty) and isinstance(new, ReverseDirectRelationProperty):
            changes.extend(self._diff_reverse_direct_relation_property(current, new, identifier))

        return changes

    def _diff_core_property(
        self,
        current: ViewCoreProperty,
        new: ViewCoreProperty,
        identifier: str,
    ) -> list[FieldChange]:
        changes: list[FieldChange] = []

        if (current.container, current.container_property_identifier) != (
            new.container,
            new.container_property_identifier,
        ):
            item_severity = self._get_container_change_severity(
                current.container,
                current.container_property_identifier,
                new.container,
                new.container_property_identifier,
            )

            if current.container != new.container:
                changes.append(
                    ChangedField(
                        field_path=self._get_path(f"{identifier}.container"),
                        item_severity=item_severity,
                        new_value=new.container,
                        current_value=current.container,
                    )
                )
            if current.container_property_identifier != new.container_property_identifier:
                changes.append(
                    ChangedField(
                        field_path=self._get_path(f"{identifier}.containerPropertyIdentifier"),
                        item_severity=item_severity,
                        new_value=new.container_property_identifier,
                        current_value=current.container_property_identifier,
                    )
                )

        if isinstance(current, ViewCorePropertyRequest) and isinstance(new, ViewCorePropertyRequest):
            if current.source != new.source:
                changes.append(
                    ChangedField(
                        field_path=self._get_path(f"{identifier}.source"),
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
        identifier: str,
    ) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if current.source != new.source:
            changes.append(
                ChangedField(
                    field_path=self._get_path(f"{identifier}.source"),
                    item_severity=SeverityType.BREAKING,
                    new_value=new.source,
                    current_value=current.source,
                )
            )
        if current.type != new.type:
            changes.append(
                ChangedField(
                    field_path=self._get_path(f"{identifier}.type"),
                    item_severity=SeverityType.WARNING,
                    new_value=new.type,
                    current_value=current.type,
                )
            )
        if current.edge_source != new.edge_source:
            changes.append(
                ChangedField(
                    field_path=self._get_path(f"{identifier}.edgeSource"),
                    item_severity=SeverityType.WARNING,
                    new_value=new.edge_source,
                    current_value=current.edge_source,
                )
            )
        if current.direction != new.direction:
            changes.append(
                ChangedField(
                    field_path=self._get_path(f"{identifier}.direction"),
                    item_severity=SeverityType.WARNING,
                    new_value=new.direction,
                    current_value=current.direction,
                )
            )
        return changes

    def _diff_reverse_direct_relation_property(
        self,
        current: ReverseDirectRelationProperty,
        new: ReverseDirectRelationProperty,
        identifier: str,
    ) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if current.source != new.source:
            changes.append(
                ChangedField(
                    field_path=self._get_path(f"{identifier}.source"),
                    item_severity=SeverityType.BREAKING,
                    new_value=new.source,
                    current_value=current.source,
                )
            )

        if current.through != new.through:
            changes.append(
                ChangedField(
                    field_path=self._get_path(f"{identifier}.through"),
                    item_severity=SeverityType.WARNING,
                    new_value=new.through,
                    current_value=current.through,
                )
            )

        return changes

    def _get_container_change_severity(
        self,
        current_container: ContainerReference,
        current_property_identifier: str,
        new_container: ContainerReference,
        new_property_identifier: str,
    ) -> SeverityType:
        current_container_property = self._get_container_property(
            current_container, current_property_identifier, self._current_container_map
        )
        new_container_property = self._get_container_property(
            new_container, new_property_identifier, self._new_container_map
        )
        if not current_container_property or not new_container_property:
            return SeverityType.BREAKING
        differ = ContainerPropertyDiffer(parent_path=None)
        changes = differ.diff(current_container_property, new_container_property, identifier="")
        return SeverityType.max_severity([item.severity for item in changes], default=SeverityType.SAFE)

    @staticmethod
    def _get_container_property(
        container_ref: ContainerReference,
        property_identifier: str,
        containers: dict[ContainerReference, ContainerRequest],
    ) -> ContainerPropertyDefinition | None:
        container = containers.get(container_ref)
        if not container:
            return None
        property_def = container.properties.get(property_identifier)
        if not property_def:
            return None
        return property_def
