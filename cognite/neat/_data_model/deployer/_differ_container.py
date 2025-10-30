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

from ._differ import ItemDiffer, field_differences
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
                    field_path="usedFor",
                    current_value=current.used_for,
                    new_value=new.used_for,
                )
            )
        changes.extend(
            field_differences(
                "properties.",
                current.properties,
                new.properties,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.BREAKING,
                differ=ContainerPropertyDiffer(),
            )
        )
        changes.extend(
            # MyPy fails to understand that ConstraintDefinition and Constraint are compatible here
            field_differences(  # type: ignore[misc]
                "constraints.",
                current.constraints,
                new.constraints,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.WARNING,
                differ=ConstraintDiffer(),
            )
        )
        changes.extend(
            # MyPy fails to understand that IndexDefinition and Index are compatible here
            field_differences(  # type: ignore[misc]
                "indexes.",
                current.indexes,
                new.indexes,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.WARNING,
                differ=IndexDiffer(),
            )
        )

        return changes


class ContainerPropertyDiffer(ItemDiffer[ContainerPropertyDefinition]):
    def diff(
        self, cdf_property: ContainerPropertyDefinition, desired_property: ContainerPropertyDefinition
    ) -> list[FieldChange]:
        changes = self._diff_name_description(cdf_property, desired_property)
        diffs = DataTypeDiffer().diff(cdf_property.type, desired_property.type)
        if diffs:
            changes.append(FieldChanges(field_path="type", changes=diffs))

        if cdf_property.immutable != desired_property.immutable:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path="immutable",
                    current_value=cdf_property.immutable,
                    new_value=desired_property.immutable,
                )
            )

        if cdf_property.nullable != desired_property.nullable:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path="nullable",
                    current_value=cdf_property.nullable,
                    new_value=desired_property.nullable,
                )
            )
        if cdf_property.auto_increment != desired_property.auto_increment:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path="autoIncrement",
                    current_value=cdf_property.auto_increment,
                    new_value=desired_property.auto_increment,
                )
            )

        if cdf_property.default_value != desired_property.default_value:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path="defaultValue",
                    current_value=str(cdf_property.default_value),
                    new_value=str(desired_property.default_value),
                )
            )
        return changes


class ConstraintDiffer(ItemDiffer[ConstraintDefinition]):
    def diff(self, cdf_constraint: ConstraintDefinition, desired_constraint: ConstraintDefinition) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if cdf_constraint.constraint_type != desired_constraint.constraint_type:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.WARNING,
                    field_path="constraintType",
                    current_value=cdf_constraint.constraint_type,
                    new_value=desired_constraint.constraint_type,
                )
            )
        if (
            isinstance(cdf_constraint, RequiresConstraintDefinition)
            and isinstance(desired_constraint, RequiresConstraintDefinition)
            and cdf_constraint.require != desired_constraint.require
        ):
            changes.append(
                ChangedField(
                    item_severity=SeverityType.WARNING,
                    field_path="require",
                    current_value=str(cdf_constraint.require),
                    new_value=str(desired_constraint.require),
                )
            )
        elif isinstance(cdf_constraint, UniquenessConstraintDefinition) and isinstance(
            desired_constraint, UniquenessConstraintDefinition
        ):
            # The order of the properties matter.
            if cdf_constraint.properties != desired_constraint.properties:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.WARNING,
                        field_path="properties",
                        current_value=str(cdf_constraint.properties),
                        new_value=str(desired_constraint.properties),
                    )
                )
            if cdf_constraint.by_space != desired_constraint.by_space:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.WARNING,
                        field_path="bySpace",
                        current_value=cdf_constraint.by_space,
                        new_value=desired_constraint.by_space,
                    )
                )
            return changes
        return changes


class IndexDiffer(ItemDiffer[IndexDefinition]):
    def diff(self, cdf_index: IndexDefinition, desired_index: IndexDefinition) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if cdf_index.index_type != desired_index.index_type:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.WARNING,
                    field_path="indexType",
                    current_value=cdf_index.index_type,
                    new_value=desired_index.index_type,
                )
            )
        else:
            if cdf_index.properties != desired_index.properties:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.WARNING,
                        field_path="properties",
                        current_value=str(cdf_index.properties),
                        new_value=str(desired_index.properties),
                    )
                )
        if isinstance(cdf_index, BtreeIndex) and isinstance(desired_index, BtreeIndex):
            if cdf_index.cursorable != desired_index.cursorable:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.WARNING,
                        field_path="cursorable",
                        current_value=cdf_index.cursorable,
                        new_value=desired_index.cursorable,
                    )
                )
            if cdf_index.by_space != desired_index.by_space:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.WARNING,
                        field_path="bySpace",
                        current_value=cdf_index.by_space,
                        new_value=desired_index.by_space,
                    )
                )
        return changes


class DataTypeDiffer(ItemDiffer[PropertyTypeDefinition]):
    def diff(self, cdf_type: PropertyTypeDefinition, desired_type: PropertyTypeDefinition) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if cdf_type.type != desired_type.type:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path="type",
                    current_value=cdf_type.type,
                    new_value=desired_type.type,
                )
            )
        if isinstance(cdf_type, ListablePropertyTypeDefinition) and isinstance(
            desired_type, ListablePropertyTypeDefinition
        ):
            changes.extend(self._check_listable_property(cdf_type, desired_type))

        if isinstance(cdf_type, TextProperty) and isinstance(desired_type, TextProperty):
            changes.extend(self._check_text_property(cdf_type, desired_type))

        if isinstance(cdf_type, FloatProperty) and isinstance(desired_type, FloatProperty):
            changes.extend(self._check_float_unit(cdf_type.unit, desired_type.unit))

        if isinstance(cdf_type, EnumProperty) and isinstance(desired_type, EnumProperty):
            changes.extend(self._check_enum_property(cdf_type, desired_type))

        return changes

    def _check_listable_property(
        self, cdf_type: ListablePropertyTypeDefinition, desired_type: ListablePropertyTypeDefinition
    ) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if cdf_type.list != desired_type.list:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING,
                    field_path="list",
                    current_value=cdf_type.list,
                    new_value=desired_type.list,
                )
            )
        if cdf_type.max_list_size != desired_type.max_list_size:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING
                    if desired_type.max_list_size is not None
                    and cdf_type.max_list_size is not None
                    and desired_type.max_list_size < cdf_type.max_list_size
                    else SeverityType.WARNING,
                    field_path="maxListSize",
                    current_value=cdf_type.max_list_size,
                    new_value=desired_type.max_list_size,
                )
            )
        return changes

    def _check_float_unit(self, cdf_unit: Unit | None, desired_unit: Unit | None) -> list[FieldChange]:
        if cdf_unit is not None and desired_unit is None:
            return [RemovedField(field_path="unit", item_severity=SeverityType.WARNING, old_value=cdf_unit)]
        elif cdf_unit is None and desired_unit is not None:
            return [AddedField(field_path="unit", item_severity=SeverityType.WARNING, new_value=desired_unit)]
        elif cdf_unit is not None and desired_unit is not None:
            changes: list[FieldChange] = []
            if cdf_unit.external_id != desired_unit.external_id:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.WARNING,
                        field_path="externalId",
                        current_value=cdf_unit.external_id,
                        new_value=desired_unit.external_id,
                    )
                )
            if cdf_unit.source_unit != desired_unit.source_unit:
                changes.append(
                    ChangedField(
                        item_severity=SeverityType.WARNING,
                        field_path="sourceUnit",
                        current_value=cdf_unit.source_unit,
                        new_value=desired_unit.source_unit,
                    )
                )
            if changes:
                return [FieldChanges(field_path="unit", changes=changes)]
        return []  # No changes

    def _check_text_property(self, cdf_type: TextProperty, desired_type: TextProperty) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if cdf_type.max_text_size != desired_type.max_text_size:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.BREAKING
                    if desired_type.max_text_size is not None
                    and cdf_type.max_text_size is not None
                    and desired_type.max_text_size < cdf_type.max_text_size
                    else SeverityType.WARNING,
                    field_path="maxTextSize",
                    current_value=cdf_type.max_text_size,
                    new_value=desired_type.max_text_size,
                )
            )
        if cdf_type.collation != desired_type.collation:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.WARNING,
                    field_path="collation",
                    current_value=cdf_type.collation,
                    new_value=desired_type.collation,
                )
            )
        return changes

    def _check_enum_property(self, cdf_type: EnumProperty, desired_type: EnumProperty) -> list[FieldChange]:
        changes: list[FieldChange] = []
        if cdf_type.unknown_value != desired_type.unknown_value:
            changes.append(
                ChangedField(
                    item_severity=SeverityType.WARNING,
                    field_path="unknownValue",
                    current_value=cdf_type.unknown_value,
                    new_value=desired_type.unknown_value,
                )
            )
        changes.extend(
            field_differences(
                "values.",
                cdf_type.values,
                desired_type.values,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.BREAKING,
                differ=EnumValueDiffer(),
            )
        )
        return changes


class EnumValueDiffer(ItemDiffer[EnumValue]):
    def diff(self, cdf_value: EnumValue, desired_value: EnumValue) -> list[FieldChange]:
        return self._diff_name_description(cdf_value, desired_value)
