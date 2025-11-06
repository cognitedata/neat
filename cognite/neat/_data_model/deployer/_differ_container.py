from cognite.neat._data_model.models.dms import (
    BtreeIndex,
    ConstraintDefinition,
    ContainerPropertyDefinition,
    ContainerRequest,
    EnumProperty,
    EnumValue,
    FloatProperty,
    IndexDefinition,
    ListablePropertyTypeDefinition,
    PropertyTypeDefinition,
    RequiresConstraintDefinition,
    TextProperty,
    UniquenessConstraintDefinition,
)
from cognite.neat._data_model.models.dms._data_types import Unit

from ._differ import ItemDiffer, ObjectDiffer, field_differences
from .data_classes import (
    AddedField,
    ChangedField,
    FieldChange,
    FieldChanges,
    RemovedField,
    SeverityType,
)


class ContainerDiffer(ItemDiffer[ContainerRequest]):
    def diff(self, current: ContainerRequest, new: ContainerRequest) -> list[FieldChange]:
        changes = self._diff_name_description(current, new)

        if current.used_for != new.used_for:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path=self._get_path("usedFor"),
                    current_value=current.used_for,
                    new_value=new.used_for,
                )
            )
        changes.extend(
            field_differences(
                "properties",
                current.properties,
                new.properties,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.BREAKING,
                differ=ContainerPropertyDiffer("properties"),
            )
        )
        changes.extend(
            # MyPy fails to understand that ConstraintDefinition and Constraint are compatible here
            field_differences(  # type: ignore[misc]
                "constraints",
                current.constraints,
                new.constraints,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.WARNING,
                differ=ConstraintDiffer("constraints"),
            )
        )
        changes.extend(
            # MyPy fails to understand that IndexDefinition and Index are compatible here
            field_differences(  # type: ignore[misc]
                "indexes",
                current.indexes,
                new.indexes,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.WARNING,
                differ=IndexDiffer("indexes"),
            )
        )

        return changes


class ContainerPropertyDiffer(ObjectDiffer[ContainerPropertyDefinition]):
    def diff(
        self, current: ContainerPropertyDefinition, new: ContainerPropertyDefinition, identifier: str
    ) -> list[FieldChange]:
        changes = self._diff_name_description(current, new, identifier=identifier)
        diffs = DataTypeDiffer(self._get_path(f"{identifier}.type")).diff(current.type, new.type)
        if diffs:
            changes.append(FieldChanges(field_path=self._get_path(f"{identifier}.type"), changes=diffs))

        if current.immutable != new.immutable:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.WARNING,
                    field_path=self._get_path(f"{identifier}.immutable"),
                    current_value=current.immutable,
                    new_value=new.immutable,
                )
            )

        if current.nullable != new.nullable:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path=self._get_path(f"{identifier}.nullable"),
                    current_value=current.nullable,
                    new_value=new.nullable,
                )
            )
        if current.auto_increment != new.auto_increment:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.WARNING,
                    field_path=self._get_path(f"{identifier}.autoIncrement"),
                    current_value=current.auto_increment,
                    new_value=new.auto_increment,
                )
            )

        if current.default_value != new.default_value:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.WARNING,
                    field_path=self._get_path(f"{identifier}.defaultValue"),
                    current_value=str(current.default_value),
                    new_value=str(new.default_value),
                )
            )
        return changes


class ConstraintDiffer(ObjectDiffer[ConstraintDefinition]):
    def diff(self, current: ConstraintDefinition, new: ConstraintDefinition, identifier: str) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if current.constraint_type != new.constraint_type:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path=self._get_path(f"{identifier}.constraintType"),
                    current_value=current.constraint_type,
                    new_value=new.constraint_type,
                )
            )
        if (
            isinstance(current, RequiresConstraintDefinition)
            and isinstance(new, RequiresConstraintDefinition)
            and current.require != new.require
        ):
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path=self._get_path(f"{identifier}.require"),
                    current_value=str(current.require),
                    new_value=str(new.require),
                )
            )
        elif isinstance(current, UniquenessConstraintDefinition) and isinstance(new, UniquenessConstraintDefinition):
            # The order of the properties matter.
            if current.properties != new.properties:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.BREAKING,
                        field_path=self._get_path(f"{identifier}.properties"),
                        current_value=str(current.properties),
                        new_value=str(new.properties),
                    )
                )
            if current.by_space != new.by_space:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.BREAKING,
                        field_path=self._get_path(f"{identifier}.bySpace"),
                        current_value=current.by_space,
                        new_value=new.by_space,
                    )
                )
            return changes
        return changes


class IndexDiffer(ObjectDiffer[IndexDefinition]):
    def diff(self, current: IndexDefinition, new: IndexDefinition, identifier: str) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if current.index_type != new.index_type:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path=self._get_path(f"{identifier}.indexType"),
                    current_value=current.index_type,
                    new_value=new.index_type,
                )
            )
        else:
            if current.properties != new.properties:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.BREAKING,
                        field_path=self._get_path(f"{identifier}.properties"),
                        current_value=str(current.properties),
                        new_value=str(new.properties),
                    )
                )
        if isinstance(current, BtreeIndex) and isinstance(new, BtreeIndex):
            if current.cursorable != new.cursorable:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.BREAKING,
                        field_path=self._get_path(f"{identifier}.cursorable"),
                        current_value=current.cursorable,
                        new_value=new.cursorable,
                    )
                )
            if current.by_space != new.by_space:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.BREAKING,
                        field_path=self._get_path(f"{identifier}.bySpace"),
                        current_value=current.by_space,
                        new_value=new.by_space,
                    )
                )
        return changes


class DataTypeDiffer(ItemDiffer[PropertyTypeDefinition]):
    def diff(self, current: PropertyTypeDefinition, new: PropertyTypeDefinition) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if current.type != new.type:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path=self._get_path("type"),
                    current_value=current.type,
                    new_value=new.type,
                )
            )
        if isinstance(current, ListablePropertyTypeDefinition) and isinstance(new, ListablePropertyTypeDefinition):
            changes.extend(self._diff_listable_property(current, new))

        if isinstance(current, TextProperty) and isinstance(new, TextProperty):
            changes.extend(self._diff_text_property(current, new))

        if isinstance(current, FloatProperty) and isinstance(new, FloatProperty):
            changes.extend(self._diff_float_unit(current.unit, new.unit))

        if isinstance(current, EnumProperty) and isinstance(new, EnumProperty):
            changes.extend(self._diff_enum_property(current, new))

        return changes

    def _diff_listable_property(
        self, current: ListablePropertyTypeDefinition, new: ListablePropertyTypeDefinition
    ) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if current.list != new.list:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path=self._get_path("list"),
                    current_value=current.list,
                    new_value=new.list,
                )
            )
        if current.max_list_size != new.max_list_size:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING
                    if new.max_list_size is not None
                    and current.max_list_size is not None
                    and new.max_list_size < current.max_list_size
                    else SeverityType.WARNING,
                    field_path=self._get_path("maxListSize"),
                    current_value=current.max_list_size,
                    new_value=new.max_list_size,
                )
            )
        return changes

    def _diff_float_unit(self, current: Unit | None, new: Unit | None) -> list[FieldChange]:
        if current is not None and new is None:
            return [
                RemovedField(
                    field_path=self._get_path("unit"), item_severity=SeverityType.WARNING, current_value=current
                )
            ]
        elif current is None and new is not None:
            return [AddedField(field_path=self._get_path("unit"), item_severity=SeverityType.WARNING, new_value=new)]
        elif current is not None and new is not None:
            changes: list[FieldChange] = []
            if current.external_id != new.external_id:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.WARNING,
                        field_path=self._get_path("unit.externalId"),
                        current_value=current.external_id,
                        new_value=new.external_id,
                    )
                )
            if current.source_unit != new.source_unit:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.WARNING,
                        field_path=self._get_path("unit.sourceUnit"),
                        current_value=current.source_unit,
                        new_value=new.source_unit,
                    )
                )
            if changes:
                return [FieldChanges(field_path=self._get_path("unit"), changes=changes)]
        return []  # No changes

    def _diff_text_property(self, current: TextProperty, new: TextProperty) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if current.max_text_size != new.max_text_size:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING
                    if new.max_text_size is not None
                    and current.max_text_size is not None
                    and new.max_text_size < current.max_text_size
                    else SeverityType.WARNING,
                    field_path=self._get_path("maxTextSize"),
                    current_value=current.max_text_size,
                    new_value=new.max_text_size,
                )
            )
        if current.collation != new.collation:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.WARNING,
                    field_path=self._get_path("collation"),
                    current_value=current.collation,
                    new_value=new.collation,
                )
            )
        return changes

    def _diff_enum_property(self, current: EnumProperty, new: EnumProperty) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if current.unknown_value != new.unknown_value:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.WARNING,
                    field_path=self._get_path("unknownValue"),
                    current_value=current.unknown_value,
                    new_value=new.unknown_value,
                )
            )
        changes.extend(
            field_differences(
                self._get_path("values"),
                current.values,
                new.values,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.BREAKING,
                differ=EnumValueDiffer(self._get_path("values")),
            )
        )
        return changes


class EnumValueDiffer(ObjectDiffer[EnumValue]):
    def diff(self, current: EnumValue, new: EnumValue, identifier: str) -> list[FieldChange]:
        return self._diff_name_description(current, new, identifier=identifier)
