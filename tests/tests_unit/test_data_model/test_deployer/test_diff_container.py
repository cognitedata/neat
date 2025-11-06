import pytest

from cognite.neat._data_model.deployer._differ_container import (
    ConstraintDiffer,
    ContainerDiffer,
    ContainerPropertyDiffer,
    DataTypeDiffer,
    EnumValueDiffer,
    IndexDiffer,
)
from cognite.neat._data_model.deployer.data_classes import (
    AddedField,
    ChangedField,
    FieldChange,
    FieldChanges,
    RemovedField,
    SeverityType,
)
from cognite.neat._data_model.models.dms import (
    BtreeIndex,
    ConstraintDefinition,
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    EnumValue,
    Float32Property,
    IndexDefinition,
    Int32Property,
    InvertedIndex,
    RequiresConstraintDefinition,
    TextProperty,
    UniquenessConstraintDefinition,
)
from cognite.neat._data_model.models.dms._data_types import EnumProperty, PropertyTypeDefinition, Unit


class TestContainerDiffer:
    PROPERTY_TO_MODIFY_ID = "toModify"
    CONSTRAINTS_TO_MODIFY_ID = "constraintToModify"
    INDEX_TO_MODIFY_ID = "indexToModify"
    cdf_container = ContainerRequest(
        space="test_space",
        externalId="test_container",
        name="Test Container",
        description="This is a test container.",
        usedFor="node",
        properties={
            PROPERTY_TO_MODIFY_ID: ContainerPropertyDefinition(type=TextProperty()),
            "toRemove": ContainerPropertyDefinition(type=TextProperty()),
        },
        constraints={
            CONSTRAINTS_TO_MODIFY_ID: UniquenessConstraintDefinition(properties=["toModify"], bySpace=True),
            "constraintToRemove": RequiresConstraintDefinition(
                require=ContainerReference(space="other_space", external_id="other_container"),
            ),
        },
        indexes={
            INDEX_TO_MODIFY_ID: BtreeIndex(properties=["toModify"], cursorable=True, bySpace=False),
            "indexToRemove": InvertedIndex(properties=["toModify"]),
        },
    )
    changed_container = ContainerRequest(
        space="test_space",
        externalId="test_container",
        name="This is an updated container",
        description="This is an update",
        usedFor="edge",
        properties={
            PROPERTY_TO_MODIFY_ID: ContainerPropertyDefinition(type=TextProperty(list=True)),
            "toAdd": ContainerPropertyDefinition(type=Int32Property()),
        },
        constraints={
            CONSTRAINTS_TO_MODIFY_ID: UniquenessConstraintDefinition(properties=["toModify"], bySpace=False),
            "constraintToAdd": RequiresConstraintDefinition(
                require=ContainerReference(space="new_space", external_id="new_container"),
            ),
        },
        indexes={
            INDEX_TO_MODIFY_ID: BtreeIndex(properties=["toModify", "toAdd"], cursorable=True, bySpace=False),
            "indexToAdd": InvertedIndex(properties=["toAdd"]),
        },
    )

    @pytest.mark.parametrize(
        "resource,expected_diff",
        [
            pytest.param(
                cdf_container,
                [],
                id="no changes",
            ),
            pytest.param(
                changed_container,
                [
                    ChangedField(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        current_value="Test Container",
                        new_value="This is an updated container",
                    ),
                    ChangedField(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        current_value="This is a test container.",
                        new_value="This is an update",
                    ),
                    ChangedField(
                        field_path="usedFor",
                        item_severity=SeverityType.BREAKING,
                        current_value="node",
                        new_value="edge",
                    ),
                    AddedField(
                        field_path="properties.toAdd",
                        item_severity=SeverityType.SAFE,
                        # MyPy do not see that we hardcoded the "toAdd" key in the changed_container
                        new_value=changed_container.properties["toAdd"],  # type: ignore[index]
                    ),
                    RemovedField(
                        field_path="properties.toRemove",
                        item_severity=SeverityType.BREAKING,
                        # See above
                        current_value=cdf_container.properties["toRemove"],  # type: ignore[index]
                    ),
                    FieldChanges(
                        field_path=f"properties.{PROPERTY_TO_MODIFY_ID}",
                        changes=[
                            FieldChanges(
                                field_path=f"properties.{PROPERTY_TO_MODIFY_ID}.type",
                                changes=[
                                    ChangedField(
                                        field_path=f"properties.{PROPERTY_TO_MODIFY_ID}.type.list",
                                        item_severity=SeverityType.BREAKING,
                                        current_value=None,
                                        new_value=True,
                                    ),
                                ],
                            )
                        ],
                    ),
                    AddedField(
                        field_path="constraints.constraintToAdd",
                        item_severity=SeverityType.SAFE,
                        # MyPy do not see that we hardcoded the "toAdd" key in the changed_container
                        new_value=changed_container.constraints["constraintToAdd"],  # type: ignore[index]
                    ),
                    RemovedField(
                        field_path="constraints.constraintToRemove",
                        item_severity=SeverityType.WARNING,
                        # See above
                        current_value=cdf_container.constraints["constraintToRemove"],  # type: ignore[index]
                    ),
                    FieldChanges(
                        field_path=f"constraints.{CONSTRAINTS_TO_MODIFY_ID}",
                        changes=[
                            ChangedField(
                                field_path=f"constraints.{CONSTRAINTS_TO_MODIFY_ID}.bySpace",
                                item_severity=SeverityType.BREAKING,
                                current_value=True,
                                new_value=False,
                            ),
                        ],
                    ),
                    AddedField(
                        field_path="indexes.indexToAdd",
                        item_severity=SeverityType.SAFE,
                        # MyPy do not see that we hardcoded the "toAdd" key in the changed_container
                        new_value=changed_container.indexes["indexToAdd"],  # type: ignore[index]
                    ),
                    RemovedField(
                        field_path="indexes.indexToRemove",
                        item_severity=SeverityType.WARNING,
                        # See above
                        current_value=cdf_container.indexes["indexToRemove"],  # type: ignore[index]
                    ),
                    FieldChanges(
                        field_path=f"indexes.{INDEX_TO_MODIFY_ID}",
                        changes=[
                            ChangedField(
                                field_path=f"indexes.{INDEX_TO_MODIFY_ID}.properties",
                                item_severity=SeverityType.BREAKING,
                                current_value="['toModify']",
                                new_value="['toModify', 'toAdd']",
                            ),
                        ],
                    ),
                ],
                id="Modify/Add/Remove properties, constraints, indexes",
            ),
        ],
    )
    def test_container_diff(self, resource: ContainerRequest, expected_diff: list[FieldChange]) -> None:
        actual_diffs = ContainerDiffer().diff(self.cdf_container, resource)
        assert expected_diff == actual_diffs

    CONTAINER_PROPERTY_ID = "container_property_diff_test"

    @pytest.mark.parametrize(
        "cdf_property,desired_property,expected_diff",
        [
            pytest.param(
                ContainerPropertyDefinition(
                    type=Float32Property(),
                    name="Name",
                    description="The name property",
                    nullable=False,
                    immutable=False,
                    defaultValue="Default Name",
                    autoIncrement=False,
                ),
                ContainerPropertyDefinition(
                    type=TextProperty(),
                    name="Name Updated",
                    description="The updated name property",
                    nullable=True,
                    immutable=True,
                    defaultValue="Updated Name",
                    autoIncrement=True,
                ),
                [
                    ChangedField(
                        field_path=f"{CONTAINER_PROPERTY_ID}.name",
                        item_severity=SeverityType.SAFE,
                        current_value="Name",
                        new_value="Name Updated",
                    ),
                    ChangedField(
                        field_path=f"{CONTAINER_PROPERTY_ID}.description",
                        item_severity=SeverityType.SAFE,
                        current_value="The name property",
                        new_value="The updated name property",
                    ),
                    FieldChanges(
                        field_path=f"{CONTAINER_PROPERTY_ID}.type",
                        changes=[
                            ChangedField(
                                field_path=f"{CONTAINER_PROPERTY_ID}.type.type",
                                item_severity=SeverityType.BREAKING,
                                current_value="float32",
                                new_value="text",
                            ),
                        ],
                    ),
                    ChangedField(
                        field_path=f"{CONTAINER_PROPERTY_ID}.immutable",
                        item_severity=SeverityType.WARNING,
                        current_value=False,
                        new_value=True,
                    ),
                    ChangedField(
                        field_path=f"{CONTAINER_PROPERTY_ID}.nullable",
                        item_severity=SeverityType.BREAKING,
                        current_value=False,
                        new_value=True,
                    ),
                    ChangedField(
                        field_path=f"{CONTAINER_PROPERTY_ID}.autoIncrement",
                        item_severity=SeverityType.WARNING,
                        current_value=False,
                        new_value=True,
                    ),
                    ChangedField(
                        field_path=f"{CONTAINER_PROPERTY_ID}.defaultValue",
                        item_severity=SeverityType.WARNING,
                        current_value="Default Name",
                        new_value="Updated Name",
                    ),
                ],
                id="ContainerPropertyDefinition change",
            ),
        ],
    )
    def test_property_diff(
        self,
        cdf_property: ContainerPropertyDefinition,
        desired_property: ContainerPropertyDefinition,
        expected_diff: list[FieldChange],
    ) -> None:
        actual = ContainerPropertyDiffer().diff(cdf_property, desired_property, self.CONTAINER_PROPERTY_ID)
        assert expected_diff == actual

    CONSTRAINT_ID = "constraint_property_diff_test"

    @pytest.mark.parametrize(
        "cdf_constraint,desired_constraint,expected_diff",
        [
            pytest.param(
                UniquenessConstraintDefinition(properties=["name"], bySpace=True),
                UniquenessConstraintDefinition(properties=["category"], bySpace=False),
                [
                    ChangedField(
                        field_path=f"{CONSTRAINT_ID}.properties",
                        item_severity=SeverityType.BREAKING,
                        current_value="['name']",
                        new_value="['category']",
                    ),
                    ChangedField(
                        field_path=f"{CONSTRAINT_ID}.bySpace",
                        item_severity=SeverityType.BREAKING,
                        current_value=True,
                        new_value=False,
                    ),
                ],
                id="UniquenessConstraintDefinition change",
            ),
            pytest.param(
                RequiresConstraintDefinition(
                    require=ContainerReference(space="other_space", external_id="other_container"),
                ),
                RequiresConstraintDefinition(
                    require=ContainerReference(space="new_space", external_id="new_container"),
                ),
                [
                    ChangedField(
                        field_path=f"{CONSTRAINT_ID}.require",
                        item_severity=SeverityType.BREAKING,
                        current_value="other_space:other_container",
                        new_value="new_space:new_container",
                    ),
                ],
                id="RequiresConstraintDefinition change",
            ),
            pytest.param(
                RequiresConstraintDefinition(
                    require=ContainerReference(space="space_a", external_id="container_a"),
                ),
                UniquenessConstraintDefinition(properties=["id"], bySpace=True),
                [
                    ChangedField(
                        field_path=f"{CONSTRAINT_ID}.constraintType",
                        item_severity=SeverityType.BREAKING,
                        current_value="requires",
                        new_value="uniqueness",
                    ),
                ],
                id="Constraint type change",
            ),
        ],
    )
    def test_constraint_diff(
        self,
        cdf_constraint: ConstraintDefinition,
        desired_constraint: ConstraintDefinition,
        expected_diff: list[FieldChange],
    ) -> None:
        actual = ConstraintDiffer().diff(cdf_constraint, desired_constraint, self.CONSTRAINT_ID)
        assert expected_diff == actual

    INDEX_ID = "index_property_definition_test"

    @pytest.mark.parametrize(
        "cdf_index,desired_index,expected_diff",
        [
            pytest.param(
                BtreeIndex(properties=["name"], cursorable=True, bySpace=False),
                BtreeIndex(properties=["category"], cursorable=False, bySpace=True),
                [
                    ChangedField(
                        field_path=f"{INDEX_ID}.properties",
                        item_severity=SeverityType.BREAKING,
                        current_value="['name']",
                        new_value="['category']",
                    ),
                    ChangedField(
                        field_path=f"{INDEX_ID}.cursorable",
                        item_severity=SeverityType.BREAKING,
                        current_value=True,
                        new_value=False,
                    ),
                    ChangedField(
                        field_path=f"{INDEX_ID}.bySpace",
                        item_severity=SeverityType.BREAKING,
                        current_value=False,
                        new_value=True,
                    ),
                ],
                id="BtreeIndex change",
            ),
            pytest.param(
                InvertedIndex(properties=["description"]),
                InvertedIndex(properties=["name", "category"]),
                [
                    ChangedField(
                        field_path=f"{INDEX_ID}.properties",
                        item_severity=SeverityType.BREAKING,
                        current_value="['description']",
                        new_value="['name', 'category']",
                    ),
                ],
                id="InvertedIndex change",
            ),
            pytest.param(
                InvertedIndex(properties=["description"]),
                BtreeIndex(properties=["description"]),
                [
                    ChangedField(
                        field_path=f"{INDEX_ID}.indexType",
                        item_severity=SeverityType.BREAKING,
                        current_value="inverted",
                        new_value="btree",
                    ),
                ],
                id="Index type change",
            ),
        ],
    )
    def test_index_diff(
        self, cdf_index: IndexDefinition, desired_index: IndexDefinition, expected_diff: list[FieldChange]
    ) -> None:
        actual = IndexDiffer().diff(cdf_index, desired_index, self.INDEX_ID)
        assert actual == expected_diff

    @pytest.mark.parametrize(
        "cdf_type,desired_type,expected_diff",
        [
            pytest.param(
                Float32Property(
                    unit=Unit(externalId="unit:meter", sourceUnit="meter"),
                    list=True,
                    maxListSize=100,
                ),
                Float32Property(
                    unit=Unit(externalId="unit:kilometer", sourceUnit="kilometer"),
                    list=False,
                    maxListSize=None,
                ),
                [
                    ChangedField(
                        field_path="list",
                        item_severity=SeverityType.BREAKING,
                        current_value=True,
                        new_value=False,
                    ),
                    ChangedField(
                        field_path="maxListSize",
                        item_severity=SeverityType.WARNING,
                        current_value=100,
                        new_value=None,
                    ),
                    FieldChanges(
                        field_path="unit",
                        changes=[
                            ChangedField(
                                field_path="unit.externalId",
                                item_severity=SeverityType.WARNING,
                                current_value="unit:meter",
                                new_value="unit:kilometer",
                            ),
                            ChangedField(
                                field_path="unit.sourceUnit",
                                item_severity=SeverityType.WARNING,
                                current_value="meter",
                                new_value="kilometer",
                            ),
                        ],
                    ),
                ],
                id="Float32Property change",
            ),
            pytest.param(
                Float32Property(),
                Float32Property(),
                [],
                id="Float property unchanged",
            ),
            pytest.param(
                Float32Property(unit=Unit(externalId="unit:meter")),
                Float32Property(unit=None),
                [
                    RemovedField(
                        field_path="unit",
                        item_severity=SeverityType.WARNING,
                        current_value=Unit(externalId="unit:meter"),
                    ),
                ],
                id="Float32Property unit removed",
            ),
            pytest.param(
                Float32Property(unit=None),
                Float32Property(unit=Unit(externalId="unit:meter")),
                [
                    AddedField(
                        field_path="unit",
                        item_severity=SeverityType.WARNING,
                        new_value=Unit(externalId="unit:meter"),
                    ),
                ],
                id="Float32Property unit removed",
            ),
            pytest.param(
                TextProperty(maxTextSize=100, collation="usc_basic"),
                TextProperty(maxTextSize=50, collation="en"),
                [
                    ChangedField(
                        field_path="maxTextSize",
                        item_severity=SeverityType.BREAKING,
                        current_value=100,
                        new_value=50,
                    ),
                    ChangedField(
                        field_path="collation",
                        item_severity=SeverityType.WARNING,
                        current_value="usc_basic",
                        new_value="en",
                    ),
                ],
                id="TextProperty change",
            ),
            pytest.param(
                EnumProperty(
                    unknownValue="unknown",
                    values={
                        "toModify": EnumValue(name="Category 1"),
                        "toRemove": EnumValue(name="Category 2"),
                    },
                ),
                EnumProperty(
                    unknownValue="unknown_updated",
                    values={
                        "toModify": EnumValue(name="Category One"),
                        "toAdd": EnumValue(name="Category 3"),
                    },
                ),
                [
                    ChangedField(
                        field_path="unknownValue",
                        item_severity=SeverityType.WARNING,
                        current_value="unknown",
                        new_value="unknown_updated",
                    ),
                    AddedField(
                        field_path="values.toAdd",
                        item_severity=SeverityType.SAFE,
                        new_value=EnumValue(name="Category 3"),
                    ),
                    RemovedField(
                        field_path="values.toRemove",
                        item_severity=SeverityType.BREAKING,
                        current_value=EnumValue(name="Category 2"),
                    ),
                    FieldChanges(
                        field_path="values.toModify",
                        changes=[
                            ChangedField(
                                field_path="values.toModify.name",
                                item_severity=SeverityType.SAFE,
                                current_value="Category 1",
                                new_value="Category One",
                            ),
                        ],
                    ),
                ],
                id="EnumProperty change",
            ),
        ],
    )
    def test_data_type_diff(
        self,
        cdf_type: PropertyTypeDefinition,
        desired_type: PropertyTypeDefinition,
        expected_diff: list[FieldChange],
    ) -> None:
        actual = DataTypeDiffer().diff(cdf_type, desired_type)
        assert expected_diff == actual

    ENUM_VALUE_ID = "enum_value_diff_test"

    @pytest.mark.parametrize(
        "cdf_value,desired_value,expected_diff",
        [
            pytest.param(
                EnumValue(
                    name="Category 1",
                    description="The first category",
                ),
                EnumValue(
                    name="Category One",
                    description="The first category updated",
                ),
                [
                    ChangedField(
                        field_path=f"{ENUM_VALUE_ID}.name",
                        item_severity=SeverityType.SAFE,
                        current_value="Category 1",
                        new_value="Category One",
                    ),
                    ChangedField(
                        field_path=f"{ENUM_VALUE_ID}.description",
                        item_severity=SeverityType.SAFE,
                        current_value="The first category",
                        new_value="The first category updated",
                    ),
                ],
                id="EnumValue change",
            )
        ],
    )
    def test_enum_value_diff(
        self, cdf_value: EnumValue, desired_value: EnumValue, expected_diff: list[FieldChange]
    ) -> None:
        actual = EnumValueDiffer().diff(cdf_value, desired_value, self.ENUM_VALUE_ID)
        assert expected_diff == actual
