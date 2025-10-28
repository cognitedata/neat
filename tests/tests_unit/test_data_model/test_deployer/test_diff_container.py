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
from cognite.neat._data_model.models.dms._data_types import EnumProperty, Float64Property, Unit


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
                defaultValue="Default Name",
                autoIncrement=False,
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
                                unit=Unit(externalId="unit:kilometer", sourceUnit="kilometer"),
                                list=False,
                                maxListSize=None,
                            ),
                            nullable=False,
                            immutable=True,
                            name="Distance in km",
                            description="The distance property in kilometers",
                            default_value=0.0,
                            auto_increment=True,
                        ),
                        "category": ContainerPropertyDefinition(
                            type=EnumProperty(
                                unknownValue="newUnknoown",
                                values={
                                    "cat1": EnumValue(name="Category One", description="The first category updated"),
                                    "cat3": EnumValue(),
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
                    # Modified property "distance" - both type changes and property metadata
                    ContainerPropertyChange(
                        field_path="properties.distance",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="name",
                                item_severity=SeverityType.SAFE,
                                old_value=None,
                                new_value="Distance in km",
                            ),
                            PrimitivePropertyChange(
                                field_path="description",
                                item_severity=SeverityType.SAFE,
                                old_value=None,
                                new_value="The distance property in kilometers",
                            ),
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
                            PrimitivePropertyChange(
                                field_path="unit.externalId",
                                item_severity=SeverityType.WARNING,
                                old_value="unit:meter",
                                new_value="unit:kilometer",
                            ),
                            PrimitivePropertyChange(
                                field_path="unit.sourceUnit",
                                item_severity=SeverityType.WARNING,
                                old_value="meter",
                                new_value="kilometer",
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
                                old_value=True,
                                new_value=False,
                            ),
                        ],
                    ),
                    # Modified property "category" - enum changes
                    ContainerPropertyChange(
                        field_path="properties.category",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="unknownValue",
                                item_severity=SeverityType.WARNING,
                                old_value="unknown",
                                new_value="newUnknoown",
                            ),
                            ContainerPropertyChange(
                                field_path="enumValues.cat1",
                                changed_items=[
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
                            ),
                            AddedProperty(
                                field_path="enumValues.cat3",
                                item_severity=SeverityType.SAFE,
                                new_value=EnumValue(),
                            ),
                            RemovedProperty(
                                field_path="enumValues.cat2",
                                item_severity=SeverityType.BREAKING,
                                old_value=EnumValue(),
                            ),
                        ],
                    ),
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
                            defaultValue="Default Name",
                            autoIncrement=False,
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
                id="comprehensive changes: add/remove/modify properties, constraints and indexes",
            ),
            pytest.param(
                ContainerRequest(
                    space="test_space",
                    externalId="test_container",
                    name="Test Container Updated",
                    description="This is a test container with updated name.",
                    usedFor="all",
                    properties={
                        "name": ContainerPropertyDefinition(
                            type=TextProperty(collation="ucs_basic", maxTextSize=50),
                            name="Name",
                            description="The name property",
                            nullable=False,
                            immutable=False,
                            defaultValue="Default Name",
                            autoIncrement=False,
                        ),
                        "distance": ContainerPropertyDefinition(type=Float64Property()),
                        "category": cdf_container.properties["category"],
                    },
                    constraints=cdf_container.constraints,
                    indexes=cdf_container.indexes,
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
                        new_value="This is a test container with updated name.",
                    ),
                    PrimitivePropertyChange(
                        field_path="usedFor",
                        item_severity=SeverityType.BREAKING,
                        old_value="node",
                        new_value="all",
                    ),
                    ContainerPropertyChange(
                        field_path="properties.name",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="maxTextSize",
                                item_severity=SeverityType.BREAKING,
                                old_value=100,
                                new_value=50,
                            ),
                            PrimitivePropertyChange(
                                field_path="collation",
                                item_severity=SeverityType.BREAKING,
                                old_value=None,
                                new_value="ucs_basic",
                            ),
                        ],
                    ),
                    ContainerPropertyChange(
                        field_path="properties.distance",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="type",
                                item_severity=SeverityType.BREAKING,
                                old_value="float32",
                                new_value="float64",
                            ),
                            PrimitivePropertyChange(
                                field_path="list",
                                item_severity=SeverityType.BREAKING,
                                old_value=True,
                                new_value=None,
                            ),
                            PrimitivePropertyChange(
                                field_path="maxListSize",
                                item_severity=SeverityType.WARNING,
                                old_value=100,
                                new_value=None,
                            ),
                            PrimitivePropertyChange(
                                field_path="immutable",
                                item_severity=SeverityType.BREAKING,
                                old_value=False,
                                new_value=None,
                            ),
                            PrimitivePropertyChange(
                                field_path="nullable",
                                item_severity=SeverityType.BREAKING,
                                old_value=True,
                                new_value=None,
                            ),
                        ],
                    ),
                ],
                id="Modify top level, change in Text Property, change DataType",
            ),
        ],
    )
    def test_diff(self, resource: ContainerRequest, expected_diff: list[PropertyChange]) -> None:
        actual_diffs = ContainerDiffer().diff(self.cdf_container, resource)
        assert actual_diffs == expected_diff
