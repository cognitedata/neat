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
    AddedProperty,
    ContainerPropertyChange,
    PrimitivePropertyChange,
    PropertyChange,
    RemovedProperty,
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
    cdf_container = ContainerRequest(
        space="test_space",
        externalId="test_container",
        name="Test Container",
        description="This is a test container.",
        usedFor="node",
        properties={
            "toModify": ContainerPropertyDefinition(type=TextProperty()),
            "toRemove": ContainerPropertyDefinition(type=TextProperty()),
        },
        constraints={
            "toModify": UniquenessConstraintDefinition(properties=["toModify"], bySpace=True),
            "toRemove": RequiresConstraintDefinition(
                require=ContainerReference(space="other_space", external_id="other_container"),
            ),
        },
        indexes={
            "toModify": BtreeIndex(properties=["toModify"], cursorable=True, bySpace=False),
            "toRemove": InvertedIndex(properties=["toModify"]),
        },
    )
    changed_container = ContainerRequest(
        space="test_space",
        externalId="test_container",
        name="This is an updated container",
        description="This is an update",
        usedFor="edge",
        properties={
            "toModify": ContainerPropertyDefinition(type=TextProperty(list=True)),
            "toAdd": ContainerPropertyDefinition(type=Int32Property()),
        },
        constraints={
            "toModify": UniquenessConstraintDefinition(properties=["toModify"], bySpace=False),
            "toAdd": RequiresConstraintDefinition(
                require=ContainerReference(space="new_space", external_id="new_container"),
            ),
        },
        indexes={
            "toModify": BtreeIndex(properties=["toModify", "toAdd"], cursorable=True, bySpace=False),
            "toAdd": InvertedIndex(properties=["toAdd"]),
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
                    PrimitivePropertyChange(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        old_value="Test Container",
                        new_value="This is an updated container",
                    ),
                    PrimitivePropertyChange(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        old_value="This is a test container.",
                        new_value="This is an update",
                    ),
                    PrimitivePropertyChange(
                        field_path="usedFor",
                        item_severity=SeverityType.BREAKING,
                        old_value="node",
                        new_value="edge",
                    ),
                    AddedProperty(
                        field_path="properties.toAdd",
                        item_severity=SeverityType.SAFE,
                        # MyPy do not see that we hardcoded the "toAdd" key in the changed_container
                        new_value=changed_container.properties["toAdd"],  # type: ignore[index]
                    ),
                    RemovedProperty(
                        field_path="properties.toRemove",
                        item_severity=SeverityType.BREAKING,
                        # See above
                        old_value=cdf_container.properties["toRemove"],  # type: ignore[index]
                    ),
                    ContainerPropertyChange(
                        field_path="properties.toModify",
                        changed_items=[
                            ContainerPropertyChange(
                                field_path="type",
                                changed_items=[
                                    PrimitivePropertyChange(
                                        field_path="list",
                                        item_severity=SeverityType.BREAKING,
                                        old_value=None,
                                        new_value=True,
                                    ),
                                ],
                            )
                        ],
                    ),
                    AddedProperty(
                        field_path="constraints.toAdd",
                        item_severity=SeverityType.SAFE,
                        # MyPy do not see that we hardcoded the "toAdd" key in the changed_container
                        new_value=changed_container.constraints["toAdd"],  # type: ignore[index]
                    ),
                    RemovedProperty(
                        field_path="constraints.toRemove",
                        item_severity=SeverityType.WARNING,
                        # See above
                        old_value=cdf_container.constraints["toRemove"],  # type: ignore[index]
                    ),
                    ContainerPropertyChange(
                        field_path="constraints.toModify",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="bySpace",
                                item_severity=SeverityType.WARNING,
                                old_value=True,
                                new_value=False,
                            ),
                        ],
                    ),
                    AddedProperty(
                        field_path="indexes.toAdd",
                        item_severity=SeverityType.SAFE,
                        # MyPy do not see that we hardcoded the "toAdd" key in the changed_container
                        new_value=changed_container.indexes["toAdd"],  # type: ignore[index]
                    ),
                    RemovedProperty(
                        field_path="indexes.toRemove",
                        item_severity=SeverityType.WARNING,
                        # See above
                        old_value=cdf_container.indexes["toRemove"],  # type: ignore[index]
                    ),
                    ContainerPropertyChange(
                        field_path="indexes.toModify",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="properties",
                                item_severity=SeverityType.WARNING,
                                old_value="['toModify']",
                                new_value="['toModify', 'toAdd']",
                            ),
                        ],
                    ),
                ],
                id="Modify/Add/Remove properties, constraints, indexes",
            ),
        ],
    )
    def test_container_diff(self, resource: ContainerRequest, expected_diff: list[PropertyChange]) -> None:
        actual_diffs = ContainerDiffer().diff(self.cdf_container, resource)
        assert expected_diff == actual_diffs

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
                    PrimitivePropertyChange(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        old_value="Name",
                        new_value="Name Updated",
                    ),
                    PrimitivePropertyChange(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        old_value="The name property",
                        new_value="The updated name property",
                    ),
                    ContainerPropertyChange(
                        field_path="type",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="type",
                                item_severity=SeverityType.BREAKING,
                                old_value="float32",
                                new_value="text",
                            ),
                        ],
                    ),
                    PrimitivePropertyChange(
                        field_path="immutable",
                        item_severity=SeverityType.BREAKING,
                        old_value=False,
                        new_value=True,
                    ),
                    PrimitivePropertyChange(
                        field_path="nullable",
                        item_severity=SeverityType.BREAKING,
                        old_value=False,
                        new_value=True,
                    ),
                    PrimitivePropertyChange(
                        field_path="autoIncrement",
                        item_severity=SeverityType.BREAKING,
                        old_value=False,
                        new_value=True,
                    ),
                    PrimitivePropertyChange(
                        field_path="defaultValue",
                        item_severity=SeverityType.BREAKING,
                        old_value="Default Name",
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
        expected_diff: list[PropertyChange],
    ) -> None:
        actual = ContainerPropertyDiffer().diff(cdf_property, desired_property)
        assert expected_diff == actual

    @pytest.mark.parametrize(
        "cdf_constraint,desired_constraint,expected_diff",
        [
            pytest.param(
                UniquenessConstraintDefinition(properties=["name"], bySpace=True),
                UniquenessConstraintDefinition(properties=["category"], bySpace=False),
                [
                    PrimitivePropertyChange(
                        field_path="properties",
                        item_severity=SeverityType.WARNING,
                        old_value="['name']",
                        new_value="['category']",
                    ),
                    PrimitivePropertyChange(
                        field_path="bySpace",
                        item_severity=SeverityType.WARNING,
                        old_value=True,
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
                    PrimitivePropertyChange(
                        field_path="require",
                        item_severity=SeverityType.WARNING,
                        old_value="other_space:other_container",
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
                    PrimitivePropertyChange(
                        field_path="constraintType",
                        item_severity=SeverityType.WARNING,
                        old_value="requires",
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
        expected_diff: list[PropertyChange],
    ) -> None:
        actual = ConstraintDiffer().diff(cdf_constraint, desired_constraint)
        assert expected_diff == actual

    @pytest.mark.parametrize(
        "cdf_index,desired_index,expected_diff",
        [
            pytest.param(
                BtreeIndex(properties=["name"], cursorable=True, bySpace=False),
                BtreeIndex(properties=["category"], cursorable=False, bySpace=True),
                [
                    PrimitivePropertyChange(
                        field_path="properties",
                        item_severity=SeverityType.WARNING,
                        old_value="['name']",
                        new_value="['category']",
                    ),
                    PrimitivePropertyChange(
                        field_path="cursorable",
                        item_severity=SeverityType.WARNING,
                        old_value=True,
                        new_value=False,
                    ),
                    PrimitivePropertyChange(
                        field_path="bySpace",
                        item_severity=SeverityType.WARNING,
                        old_value=False,
                        new_value=True,
                    ),
                ],
                id="BtreeIndex change",
            ),
            pytest.param(
                InvertedIndex(properties=["description"]),
                InvertedIndex(properties=["name", "category"]),
                [
                    PrimitivePropertyChange(
                        field_path="properties",
                        item_severity=SeverityType.WARNING,
                        old_value="['description']",
                        new_value="['name', 'category']",
                    ),
                ],
                id="InvertedIndex change",
            ),
            pytest.param(
                InvertedIndex(properties=["description"]),
                BtreeIndex(properties=["description"]),
                [
                    PrimitivePropertyChange(
                        field_path="indexType",
                        item_severity=SeverityType.WARNING,
                        old_value="inverted",
                        new_value="btree",
                    ),
                ],
                id="Index type change",
            ),
        ],
    )
    def test_index_diff(
        self, cdf_index: IndexDefinition, desired_index: IndexDefinition, expected_diff: list[PropertyChange]
    ) -> None:
        actual = IndexDiffer().diff(cdf_index, desired_index)
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
                    PrimitivePropertyChange(
                        field_path="list",
                        item_severity=SeverityType.BREAKING,
                        old_value=True,
                        new_value=False,
                    ),
                    PrimitivePropertyChange(
                        field_path="maxListSize",
                        item_severity=SeverityType.WARNING,
                        old_value=100,
                        new_value=None,
                    ),
                    ContainerPropertyChange(
                        field_path="unit",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="externalId",
                                item_severity=SeverityType.WARNING,
                                old_value="unit:meter",
                                new_value="unit:kilometer",
                            ),
                            PrimitivePropertyChange(
                                field_path="sourceUnit",
                                item_severity=SeverityType.WARNING,
                                old_value="meter",
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
                    RemovedProperty(
                        field_path="unit",
                        item_severity=SeverityType.WARNING,
                        old_value=Unit(externalId="unit:meter"),
                    ),
                ],
                id="Float32Property unit removed",
            ),
            pytest.param(
                Float32Property(unit=None),
                Float32Property(unit=Unit(externalId="unit:meter")),
                [
                    AddedProperty(
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
                    PrimitivePropertyChange(
                        field_path="maxTextSize",
                        item_severity=SeverityType.BREAKING,
                        old_value=100,
                        new_value=50,
                    ),
                    PrimitivePropertyChange(
                        field_path="collation",
                        item_severity=SeverityType.WARNING,
                        old_value="usc_basic",
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
                    PrimitivePropertyChange(
                        field_path="unknownValue",
                        item_severity=SeverityType.WARNING,
                        old_value="unknown",
                        new_value="unknown_updated",
                    ),
                    AddedProperty(
                        field_path="values.toAdd",
                        item_severity=SeverityType.SAFE,
                        new_value=EnumValue(name="Category 3"),
                    ),
                    RemovedProperty(
                        field_path="values.toRemove",
                        item_severity=SeverityType.BREAKING,
                        old_value=EnumValue(name="Category 2"),
                    ),
                    ContainerPropertyChange(
                        field_path="values.toModify",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="name",
                                item_severity=SeverityType.SAFE,
                                old_value="Category 1",
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
        expected_diff: list[PropertyChange],
    ) -> None:
        actual = DataTypeDiffer().diff(cdf_type, desired_type)
        assert expected_diff == actual

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
                    PrimitivePropertyChange(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        old_value="Category 1",
                        new_value="Category One",
                    ),
                    PrimitivePropertyChange(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        old_value="The first category",
                        new_value="The first category updated",
                    ),
                ],
                id="EnumValue change",
            )
        ],
    )
    def test_enum_value_diff(
        self, cdf_value: EnumValue, desired_value: EnumValue, expected_diff: list[PropertyChange]
    ) -> None:
        actual = EnumValueDiffer().diff(cdf_value, desired_value)
        assert expected_diff == actual
