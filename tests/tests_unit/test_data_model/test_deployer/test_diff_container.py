import pytest

from cognite.neat._data_model.deployer._differ_container import ContainerDiffer
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
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    EnumValue,
    Float32Property,
    Int32Property,
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
                    name="Test Container",
                    description="This is a test container.",
                    usedFor="node",
                    properties={
                        # "name" removed
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
                        # Added new property
                        "count": ContainerPropertyDefinition(
                            type=Int32Property(),
                            name="Count",
                            description="A count property",
                            nullable=True,
                            immutable=False,
                        ),
                    },
                    constraints={
                        # Modified constraint: changed require reference
                        "req1": RequiresConstraintDefinition(
                            require=ContainerReference(space="new_space", external_id="new_container"),
                        ),
                        # "uniq1" removed
                        # Added new constraint
                        "uniq2": UniquenessConstraintDefinition(
                            properties=["category"],
                            bySpace=False,
                        ),
                    },
                    indexes={
                        # Modified index: changed properties and cursorable
                        "idx1": BtreeIndex(
                            properties=["category"],
                            cursorable=False,
                            bySpace=False,
                        ),
                        # "idx2" removed
                        # Added new index
                        "idx3": InvertedIndex(
                            properties=["count"],
                        ),
                    },
                ),
                [
                    # Added new property "count"
                    AddedProperty(
                        field_path="properties.count",
                        item_severity=SeverityType.SAFE,
                        new_value=ContainerPropertyDefinition(
                            type=Int32Property(),
                            name="Count",
                            description="A count property",
                            nullable=True,
                            immutable=False,
                        ),
                    ),
                    # Removed property "name"
                    RemovedProperty(
                        field_path="properties.name",
                        item_severity=SeverityType.BREAKING,
                        old_value=ContainerPropertyDefinition(
                            type=TextProperty(maxTextSize=100),
                            name="Name",
                            description="The name property",
                            nullable=False,
                            immutable=False,
                            default_value="Default Name",
                            auto_increment=False,
                        ),
                    ),
                    # Modified constraint "req1"
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
                    # Added new constraint "uniq2"
                    AddedProperty(
                        field_path="constraints.uniq2",
                        item_severity=SeverityType.SAFE,
                        new_value=UniquenessConstraintDefinition(
                            properties=["category"],
                            bySpace=False,
                        ),
                    ),
                    # Removed constraint "uniq1"
                    RemovedProperty(
                        field_path="constraints.uniq1",
                        item_severity=SeverityType.WARNING,
                        old_value=UniquenessConstraintDefinition(
                            properties=["name"],
                            bySpace=True,
                        ),
                    ),
                    # Modified index "idx1"
                    ContainerPropertyChange(
                        field_path="indexes.idx1",
                        changed_items=[
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
                        ],
                    ),
                    # Added new index "idx3"
                    AddedProperty(
                        field_path="indexes.idx3",
                        item_severity=SeverityType.SAFE,
                        new_value=InvertedIndex(
                            properties=["count"],
                        ),
                    ),
                    # Removed index "idx2"
                    RemovedProperty(
                        field_path="indexes.idx2",
                        item_severity=SeverityType.WARNING,
                        old_value=InvertedIndex(
                            properties=["category", "distance"],
                        ),
                    ),
                ],
                id="comprehensive changes: add/remove properties, modify/add/remove constraints and indexes",
            ),
        ],
    )
    def test_diff(self, resource: ContainerRequest, expected_diff: list[PropertyChange]) -> None:
        actual_diffs = ContainerDiffer().diff(
            self.cdf_container,
            resource,
        )
        assert actual_diffs == expected_diff
