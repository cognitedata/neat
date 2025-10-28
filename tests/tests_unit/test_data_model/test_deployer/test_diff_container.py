import pytest

from cognite.neat._data_model.deployer._differ_container import ContainerDiffer
from cognite.neat._data_model.deployer.data_classes import (
    AddedProperty,
    ContainerPropertyChange,
    PrimitivePropertyChange,
    PropertyChange,
    SeverityType,
)
from cognite.neat._data_model.models.dms import (
    BtreeIndex,
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    RequiresConstraintDefinition,
    TextProperty,
    UniquenessConstraintDefinition,
)


class TestContainerDiffer:
    cdf_container = ContainerRequest(
        space="test_space",
        externalId="test_container",
        name="Test Container",
        description="This is a test container.",
        usedFor="node",
        properties={
            "name": ContainerPropertyDefinition(
                type=TextProperty(type="text"),
                name="Name",
                description="The name property",
                nullable=False,
                immutable=False,
            ),
            "description": ContainerPropertyDefinition(
                type=TextProperty(type="text"),
                name="Description",
                description="The description property",
                nullable=True,
                immutable=False,
            ),
        },
        constraints={
            "req1": RequiresConstraintDefinition(
                constraintType="requires",
                require=ContainerReference(space="other_space", external_id="other_container"),
            ),
            "uniq1": UniquenessConstraintDefinition(
                constraintType="uniqueness",
                properties=["name"],
                bySpace=True,
            ),
        },
        indexes={
            "idx1": BtreeIndex(
                indexType="btree",
                properties=["name"],
                cursorable=True,
                bySpace=False,
            ),
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
                ContainerRequest(
                    space="test_space",
                    externalId="test_container",
                    name="Test Container Updated",
                    description="This is an updated test container.",
                    usedFor="node",
                    properties={
                        "name": ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                            name="Name",
                            description="The name property",
                            nullable=False,
                            immutable=False,
                        ),
                        "description": ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                            name="Description",
                            description="The description property",
                            nullable=True,
                            immutable=False,
                        ),
                    },
                    constraints={
                        "req1": RequiresConstraintDefinition(
                            constraintType="requires",
                            require=ContainerReference(space="other_space", external_id="other_container"),
                        ),
                        "uniq1": UniquenessConstraintDefinition(
                            constraintType="uniqueness",
                            properties=["name"],
                            bySpace=True,
                        ),
                    },
                    indexes={
                        "idx1": BtreeIndex(
                            indexType="btree",
                            properties=["name"],
                            cursorable=True,
                            bySpace=False,
                        ),
                    },
                ),
                [
                    PrimitivePropertyChange(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        old_value="Test Container",
                        new_value="Test Container Updated",
                    ),
                    PrimitivePropertyChange(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        old_value="This is a test container.",
                        new_value="This is an updated test container.",
                    ),
                ],
                id="name and description changed",
            ),
            pytest.param(
                ContainerRequest(
                    space="test_space",
                    externalId="test_container",
                    name="Test Container",
                    description="This is a test container.",
                    usedFor="all",
                    properties={
                        "name": ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                            name="Name",
                            description="The name property",
                            nullable=False,
                            immutable=False,
                        ),
                        "description": ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                            name="Description",
                            description="The description property",
                            nullable=True,
                            immutable=False,
                        ),
                    },
                    constraints={
                        "req1": RequiresConstraintDefinition(
                            constraintType="requires",
                            require=ContainerReference(space="other_space", external_id="other_container"),
                        ),
                        "uniq1": UniquenessConstraintDefinition(
                            constraintType="uniqueness",
                            properties=["name"],
                            bySpace=True,
                        ),
                    },
                    indexes={
                        "idx1": BtreeIndex(
                            indexType="btree",
                            properties=["name"],
                            cursorable=True,
                            bySpace=False,
                        ),
                    },
                ),
                [
                    PrimitivePropertyChange(
                        field_path="usedFor",
                        item_severity=SeverityType.BREAKING,
                        old_value="node",
                        new_value="all",
                    ),
                ],
                id="used_for changed",
            ),
            pytest.param(
                ContainerRequest(
                    space="test_space",
                    externalId="test_container",
                    name="Test Container",
                    description="This is a test container.",
                    usedFor="node",
                    properties={
                        "name": ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                            name="Name Updated",
                            description="The updated name property",
                            nullable=True,
                            immutable=True,
                        ),
                        "description": ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                            name="Description",
                            description="The description property",
                            nullable=True,
                            immutable=False,
                        ),
                        "age": ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                            name="Age",
                            description="The age property",
                            nullable=True,
                            immutable=False,
                        ),
                    },
                    constraints={
                        "req1": RequiresConstraintDefinition(
                            constraintType="requires",
                            require=ContainerReference(space="other_space", external_id="other_container"),
                        ),
                        "uniq1": UniquenessConstraintDefinition(
                            constraintType="uniqueness",
                            properties=["name"],
                            bySpace=True,
                        ),
                    },
                    indexes={
                        "idx1": BtreeIndex(
                            indexType="btree",
                            properties=["name"],
                            cursorable=True,
                            bySpace=False,
                        ),
                    },
                ),
                [
                    ContainerPropertyChange(
                        field_path="properties.name",
                        changed_items=[
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
                        ],
                    ),
                    AddedProperty(
                        field_path="properties.age",
                        item_severity=SeverityType.SAFE,
                        new_value=ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                            name="Age",
                            description="The age property",
                            nullable=True,
                            immutable=False,
                        ),
                    ),
                ],
                id="property changes and addition",
            ),
            pytest.param(
                ContainerRequest(
                    space="test_space",
                    externalId="test_container",
                    name="Test Container",
                    description="This is a test container.",
                    usedFor="node",
                    properties={
                        "name": ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                            name="Name",
                            description="The name property",
                            nullable=False,
                            immutable=False,
                        ),
                        "description": ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                            name="Description",
                            description="The description property",
                            nullable=True,
                            immutable=False,
                        ),
                    },
                    constraints={
                        "req1": RequiresConstraintDefinition(
                            constraintType="requires",
                            require=ContainerReference(space="new_space", external_id="new_container"),
                        ),
                        "uniq1": UniquenessConstraintDefinition(
                            constraintType="uniqueness",
                            properties=["name", "description"],
                            bySpace=False,
                        ),
                        "uniq2": UniquenessConstraintDefinition(
                            constraintType="uniqueness",
                            properties=["name"],
                            bySpace=True,
                        ),
                    },
                    indexes={
                        "idx1": BtreeIndex(
                            indexType="btree",
                            properties=["name"],
                            cursorable=True,
                            bySpace=False,
                        ),
                    },
                ),
                [
                    ContainerPropertyChange(
                        field_path="constraints.req1",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="require",
                                item_severity=SeverityType.WARNING,
                                old_value="other_space:other_container",
                                new_value="new_space:new_container",
                            ),
                        ],
                    ),
                    ContainerPropertyChange(
                        field_path="constraints.uniq1",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="properties",
                                item_severity=SeverityType.WARNING,
                                old_value="['name']",
                                new_value="['name', 'description']",
                            ),
                            PrimitivePropertyChange(
                                field_path="bySpace",
                                item_severity=SeverityType.WARNING,
                                old_value=True,
                                new_value=False,
                            ),
                        ],
                    ),
                    AddedProperty(
                        field_path="constraints.uniq2",
                        item_severity=SeverityType.SAFE,
                        new_value=UniquenessConstraintDefinition(
                            constraintType="uniqueness",
                            properties=["name"],
                            bySpace=True,
                        ),
                    ),
                ],
                id="constraint changes and addition",
            ),
            pytest.param(
                ContainerRequest(
                    space="test_space",
                    externalId="test_container",
                    name="Test Container",
                    description="This is a test container.",
                    usedFor="node",
                    properties={
                        "name": ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                            name="Name",
                            description="The name property",
                            nullable=False,
                            immutable=False,
                        ),
                        "description": ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                            name="Description",
                            description="The description property",
                            nullable=True,
                            immutable=False,
                        ),
                    },
                    constraints={
                        "req1": RequiresConstraintDefinition(
                            constraintType="requires",
                            require=ContainerReference(space="other_space", external_id="other_container"),
                        ),
                        "uniq1": UniquenessConstraintDefinition(
                            constraintType="uniqueness",
                            properties=["name"],
                            bySpace=True,
                        ),
                    },
                    indexes={
                        "idx1": BtreeIndex(
                            indexType="btree",
                            properties=["name", "description"],
                            cursorable=False,
                            bySpace=True,
                        ),
                        "idx2": BtreeIndex(
                            indexType="btree",
                            properties=["description"],
                            cursorable=True,
                            bySpace=False,
                        ),
                    },
                ),
                [
                    ContainerPropertyChange(
                        field_path="indexes.idx1",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="properties",
                                item_severity=SeverityType.WARNING,
                                old_value="['name']",
                                new_value="['name', 'description']",
                            ),
                            PrimitivePropertyChange(
                                field_path="cursorable",
                                item_severity=SeverityType.WARNING,
                                old_value=True,
                                new_value=False,
                            ),
                            PrimitivePropertyChange(
                                field_path="unique",
                                item_severity=SeverityType.WARNING,
                                old_value=False,
                                new_value=True,
                            ),
                        ],
                    ),
                    AddedProperty(
                        field_path="indexes.idx2",
                        item_severity=SeverityType.SAFE,
                        new_value=BtreeIndex(
                            indexType="btree",
                            properties=["description"],
                            cursorable=True,
                            bySpace=False,
                        ),
                    ),
                ],
                id="index changes and addition",
            ),
        ],
    )
    def test_diff(self, resource: ContainerRequest, expected_diff: list[PropertyChange]) -> None:
        actual_diffs = ContainerDiffer().diff(
            self.cdf_container,
            resource,
        )
        assert actual_diffs == expected_diff
