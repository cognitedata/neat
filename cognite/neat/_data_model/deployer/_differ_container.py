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

from ._differ import ItemDiffer, diff_container
from .data_classes import (
    ContainerPropertyChange,
    PrimitivePropertyChange,
    PropertyChange,
    SeverityType,
)


class ContainerDiffer(ItemDiffer[ContainerRequest]):
    def diff(self, cdf_container: ContainerRequest, container: ContainerRequest) -> list[PropertyChange]:
        changes = self._check_name_description(cdf_container, container)

        if cdf_container.used_for != container.used_for:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.BREAKING,
                    field_path="usedFor",
                    old_value=cdf_container.used_for,
                    new_value=container.used_for,
                )
            )
        changes.extend(
            diff_container(
                "properties.",
                cdf_container.properties,
                container.properties,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.BREAKING,
                differ=ContainerPropertyDiffer(),
            )
        )
        changes.extend(
            # MyPy fails to understand that ConstraintDefinition and Constraint are compatible here
            diff_container(  # type: ignore[misc]
                "constraints.",
                cdf_container.constraints,
                container.constraints,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.WARNING,
                differ=ConstraintDiffer(),
            )
        )
        changes.extend(
            # MyPy fails to understand that IndexDefinition and Index are compatible here
            diff_container(  # type: ignore[misc]
                "indexes.",
                cdf_container.indexes,
                container.indexes,
                add_severity=SeverityType.SAFE,
                remove_severity=SeverityType.WARNING,
                differ=IndexDiffer(),
            )
        )

        return changes


class ContainerPropertyDiffer(ItemDiffer[ContainerPropertyDefinition]):
    def diff(
        self, cdf_property: ContainerPropertyDefinition, desired_property: ContainerPropertyDefinition
    ) -> list[PropertyChange]:
        changes = self._check_name_description(cdf_property, desired_property)
        diffs = DataTypeDiffer().diff(cdf_property.type, desired_property.type)
        if diffs:
            changes.append(ContainerPropertyChange(field_path="type", changed_items=diffs))

        if cdf_property.immutable != desired_property.immutable:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.BREAKING,
                    field_path="immutable",
                    old_value=cdf_property.immutable,
                    new_value=desired_property.immutable,
                )
            )

        if cdf_property.nullable != desired_property.nullable:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.BREAKING,
                    field_path="nullable",
                    old_value=cdf_property.nullable,
                    new_value=desired_property.nullable,
                )
            )
        if cdf_property.auto_increment != desired_property.auto_increment:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.BREAKING,
                    field_path="autoIncrement",
                    old_value=cdf_property.auto_increment,
                    new_value=desired_property.auto_increment,
                )
            )

        if cdf_property.default_value != desired_property.default_value:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.BREAKING,
                    field_path="defaultValue",
                    old_value=str(cdf_property.default_value),
                    new_value=str(desired_property.default_value),
                )
            )
        return changes


class ConstraintDiffer(ItemDiffer[ConstraintDefinition]):
    def diff(
        self, cdf_constraint: ConstraintDefinition, desired_constraint: ConstraintDefinition
    ) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        if cdf_constraint.constraint_type != desired_constraint.constraint_type:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.WARNING,
                    field_path="constraintType",
                    old_value=cdf_constraint.constraint_type,
                    new_value=desired_constraint.constraint_type,
                )
            )
        if (
            isinstance(cdf_constraint, RequiresConstraintDefinition)
            and isinstance(desired_constraint, RequiresConstraintDefinition)
            and cdf_constraint.require != desired_constraint.require
        ):
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.WARNING,
                    field_path="require",
                    old_value=str(cdf_constraint.require),
                    new_value=str(desired_constraint.require),
                )
            )
        elif isinstance(cdf_constraint, UniquenessConstraintDefinition) and isinstance(
            desired_constraint, UniquenessConstraintDefinition
        ):
            # The order of the properties matter.
            if cdf_constraint.properties != desired_constraint.properties:
                changes.append(
                    PrimitivePropertyChange(
                        item_severity=SeverityType.WARNING,
                        field_path="properties",
                        old_value=str(cdf_constraint.properties),
                        new_value=str(desired_constraint.properties),
                    )
                )
            if cdf_constraint.by_space != desired_constraint.by_space:
                changes.append(
                    PrimitivePropertyChange(
                        item_severity=SeverityType.WARNING,
                        field_path="bySpace",
                        old_value=cdf_constraint.by_space,
                        new_value=desired_constraint.by_space,
                    )
                )
            return changes
        return changes


class IndexDiffer(ItemDiffer[IndexDefinition]):
    def diff(self, cdf_index: IndexDefinition, desired_index: IndexDefinition) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        if cdf_index.index_type != desired_index.index_type:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.WARNING,
                    field_path="indexType",
                    old_value=cdf_index.index_type,
                    new_value=desired_index.index_type,
                )
            )
        else:
            if cdf_index.properties != desired_index.properties:
                changes.append(
                    PrimitivePropertyChange(
                        item_severity=SeverityType.WARNING,
                        field_path="properties",
                        old_value=str(cdf_index.properties),
                        new_value=str(desired_index.properties),
                    )
                )
        if isinstance(cdf_index, BtreeIndex) and isinstance(desired_index, BtreeIndex):
            if cdf_index.cursorable != desired_index.cursorable:
                changes.append(
                    PrimitivePropertyChange(
                        item_severity=SeverityType.WARNING,
                        field_path="cursorable",
                        old_value=cdf_index.cursorable,
                        new_value=desired_index.cursorable,
                    )
                )
            if cdf_index.by_space != desired_index.by_space:
                changes.append(
                    PrimitivePropertyChange(
                        item_severity=SeverityType.WARNING,
                        field_path="bySpace",
                        old_value=cdf_index.by_space,
                        new_value=desired_index.by_space,
                    )
                )
        return changes


class DataTypeDiffer(ItemDiffer[PropertyTypeDefinition]):
    def diff(self, cdf_type: PropertyTypeDefinition, desired_type: PropertyTypeDefinition) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        if cdf_type.type != desired_type.type:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.BREAKING,
                    field_path="type",
                    old_value=cdf_type.type,
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
            changes.extend(self._check_float_property(cdf_type, desired_type))

        if isinstance(cdf_type, EnumProperty) and isinstance(desired_type, EnumProperty):
            changes.extend(self._check_enum_property(cdf_type, desired_type))

        return changes

    def _check_listable_property(
        self, cdf_type: ListablePropertyTypeDefinition, desired_type: ListablePropertyTypeDefinition
    ) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        if cdf_type.list != desired_type.list:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.BREAKING,
                    field_path="list",
                    old_value=cdf_type.list,
                    new_value=desired_type.list,
                )
            )
        if cdf_type.max_list_size != desired_type.max_list_size:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.BREAKING
                    if desired_type.max_list_size is not None
                    and cdf_type.max_list_size is not None
                    and desired_type.max_list_size < cdf_type.max_list_size
                    else SeverityType.WARNING,
                    field_path="maxListSize",
                    old_value=cdf_type.max_list_size,
                    new_value=desired_type.max_list_size,
                )
            )
        return changes

    def _check_float_property(self, cdf_type: FloatProperty, desired_type: FloatProperty) -> list[PropertyChange]:
        if cdf_type.unit is None or desired_type.unit is None:
            return []
        changes: list[PropertyChange] = []
        if cdf_type.unit.external_id != desired_type.unit.external_id:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.WARNING,
                    field_path="unit.externalId",
                    old_value=cdf_type.unit.external_id,
                    new_value=desired_type.unit.external_id,
                )
            )
        if cdf_type.unit.source_unit != desired_type.unit.source_unit:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.WARNING,
                    field_path="unit.sourceUnit",
                    old_value=cdf_type.unit.source_unit,
                    new_value=desired_type.unit.source_unit,
                )
            )
        return changes

    def _check_text_property(self, cdf_type: TextProperty, desired_type: TextProperty) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        if cdf_type.max_text_size != desired_type.max_text_size:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.BREAKING
                    if desired_type.max_text_size is not None
                    and cdf_type.max_text_size is not None
                    and desired_type.max_text_size < cdf_type.max_text_size
                    else SeverityType.WARNING,
                    field_path="maxTextSize",
                    old_value=cdf_type.max_text_size,
                    new_value=desired_type.max_text_size,
                )
            )
        if cdf_type.collation != desired_type.collation:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.WARNING,
                    field_path="collation",
                    old_value=cdf_type.collation,
                    new_value=desired_type.collation,
                )
            )
        return changes

    def _check_enum_property(self, cdf_type: EnumProperty, desired_type: EnumProperty) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        if cdf_type.unknown_value != desired_type.unknown_value:
            changes.append(
                PrimitivePropertyChange(
                    item_severity=SeverityType.WARNING,
                    field_path="unknownValue",
                    old_value=cdf_type.unknown_value,
                    new_value=desired_type.unknown_value,
                )
            )
        changes.extend(
            diff_container(
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
    def diff(self, cdf_value: EnumValue, desired_value: EnumValue) -> list[PropertyChange]:
        return self._check_name_description(cdf_value, desired_value)
