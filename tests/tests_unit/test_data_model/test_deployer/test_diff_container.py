import pytest

from cognite.neat._data_model.deployer._differ_container import ContainerDiffer
from cognite.neat._data_model.deployer.data_classes import (
    PrimitivePropertyChange,
    PropertyChange,
    SeverityType,
)
from cognite.neat._data_model.models.dms import (
    BtreeIndex,
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    EnumValue,
    Float32Property,
    InvertedIndex,
    RequiresConstraintDefinition,
    TextProperty,
    UniquenessConstraintDefinition,
)
from cognite.neat._data_model.models.dms._data_types import EnumProperty, Unit


class TestContainerDiffer:
    cdf_container = ContainerRequest(
        space="test_space",
        externalId="test_container",
        name="Test Container",
        description="This is a test container.",
        usedFor="node",
        properties={
            "name": ContainerPropertyDefinition(
                type=TextProperty(maxTextSize=100),
                name="Name",
                description="The name property",
                nullable=False,
                immutable=False,
                default_value="Default Name",
                auto_increment=False,
            ),
            "distance": ContainerPropertyDefinition(
                type=Float32Property(
                    unit=Unit(externalId="unit:meter", sourceUnit="meter"), list=True, maxListSize=100
                ),
                nullable=True,
                immutable=False,
            ),
            "category": ContainerPropertyDefinition(
                type=EnumProperty(
                    unknownValue="unknown",
                    values={
                        "cat1": EnumValue(name="Category 1", description="The first category"),
                        "cat2": EnumValue(),
                    },
                )
            ),
        },
        constraints={
            "req1": RequiresConstraintDefinition(
                require=ContainerReference(space="other_space", external_id="other_container"),
            ),
            "uniq1": UniquenessConstraintDefinition(
                properties=["name"],
                bySpace=True,
            ),
        },
        indexes={
            "idx1": BtreeIndex(
                properties=["name"],
                cursorable=True,
                bySpace=False,
            ),
            "idx2": InvertedIndex(
                properties=["category", "distance"],
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
                    usedFor="edge",
                    properties={
                        "newProperty": ContainerPropertyDefinition(
                            type=TextProperty(type="text"),
                        ),
                        "distance": ContainerPropertyDefinition(
                            type=Float32Property(
                                unit=Unit(externalId="unit:kilometer", sourceUnit="meter"), list=False, maxListSize=None
                            ),
                            name="Updated name",
                            description="Updated description",
                            nullable=True,
                            immutable=False,
                            default_value="New default",
                            auto_increment=True,
                        ),
                    },
                    constraints={
                        "req1": RequiresConstraintDefinition(
                            require=ContainerReference(space="other_space", external_id="new_container"),
                        ),
                        "uniq1": UniquenessConstraintDefinition(
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
        ],
    )
    def test_diff(self, resource: ContainerRequest, expected_diff: list[PropertyChange]) -> None:
        actual_diffs = ContainerDiffer().diff(
            self.cdf_container,
            resource,
        )
        assert actual_diffs == expected_diff
