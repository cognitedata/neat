from collections.abc import Iterable
from typing import cast
from uuid import uuid4

import pytest

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer._differ_container import ContainerDiffer
from cognite.neat._data_model.deployer.data_classes import (
    humanize_changes,
)
from cognite.neat._data_model.models.dms import (
    BooleanProperty,
    BtreeIndex,
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    EnumProperty,
    EnumValue,
    Float32Property,
    Int32Property,
    InvertedIndex,
    RequiresConstraintDefinition,
    SpaceResponse,
    TextProperty,
    UniquenessConstraintDefinition,
)
from cognite.neat._data_model.models.dms._data_types import Unit

from .utils import assert_allowed_change, assert_change

TEXT_PROPERTY_ID = "textProperty"
LISTABLE_INT_PROPERTY_ID = "listableProperty"
LISTABLE_BOOL_PROPERTY_ID = "listableBoolProperty"
FLOAT_PROPERTY_ID = "floatProperty"
ENUM_PROPERTY_ID = "enumProperty"
UNIQUENESS_CONSTRAINT_ID = "uniqueConstraint"
REQUIRES_CONSTRAINT_ID = "requiresConstraint"
BTREE_INDEX_ID = "btreeIndex"
INVERTED_INDEX_ID = "invertedIndex"


@pytest.fixture(scope="function")
def current_container(neat_test_space: SpaceResponse, neat_client: NeatClient) -> Iterable[ContainerRequest]:
    """This is the container in CDF before changes."""
    # We use a random ID to avoid conflicts between tests
    random_id = str(uuid4()).replace("-", "_")
    container = ContainerRequest(
        space=neat_test_space.space,
        externalId=f"test_container_{random_id}",
        name="Initial name",
        description="Initial description",
        usedFor="node",
        properties={
            TEXT_PROPERTY_ID: ContainerPropertyDefinition(
                type=TextProperty(max_text_size=100, collation="ucs_basic"),
                name="Text Property",
                description="A text property",
                immutable=False,
                nullable=True,
                defaultValue="default text",
            ),
            LISTABLE_INT_PROPERTY_ID: ContainerPropertyDefinition(
                type=Int32Property(list=True, maxListSize=10),
                autoIncrement=False,
                nullable=False,
            ),
            LISTABLE_BOOL_PROPERTY_ID: ContainerPropertyDefinition(type=BooleanProperty(list=True)),
            FLOAT_PROPERTY_ID: ContainerPropertyDefinition(
                type=Float32Property(unit=Unit(externalId="length:m", sourceUnit="meters"))
            ),
            ENUM_PROPERTY_ID: ContainerPropertyDefinition(
                type=EnumProperty(
                    unknownValue="UNKNOWN",
                    values={
                        "toRemove": EnumValue(),
                        "toModify": EnumValue(),
                        "UNKNOWN": EnumValue(),
                    },
                )
            ),
        },
        constraints={
            UNIQUENESS_CONSTRAINT_ID: UniquenessConstraintDefinition(properties=[TEXT_PROPERTY_ID], bySpace=True),
            REQUIRES_CONSTRAINT_ID: RequiresConstraintDefinition(
                require=ContainerReference(space="cdf_cdm", external_id="CogniteDescribable")
            ),
        },
        indexes={
            BTREE_INDEX_ID: BtreeIndex(properties=[TEXT_PROPERTY_ID], bySpace=True, cursorable=True),
            INVERTED_INDEX_ID: InvertedIndex(properties=[LISTABLE_INT_PROPERTY_ID]),
        },
    )
    try:
        created = neat_client.containers.apply([container])
        if len(created) != 1:
            raise AssertionError("Failed to set up container for testing how the container API reacts to changes.")
        created_container = created[0]
        yield created_container.as_request()
    finally:
        neat_client.containers.delete([container.as_reference()])


class TestContainerDiffer:
    def test_diff_no_changes(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_container = current_container.model_copy(deep=True)
        diffs = ContainerDiffer().diff(current_container, new_container)
        if len(diffs) != 0:
            messages = humanize_changes(diffs)
            raise AssertionError(f"Updating a container without changes should yield no diffs. Got:\n{messages}")

        assert_allowed_change(new_container, neat_client.containers, "no changes", expect_silent_ignore=False)

    def test_diff_used_for(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_container = current_container.model_copy(deep=True, update={"used_for": "edge"})
        assert_change(ContainerDiffer(), current_container, new_container, neat_client.containers, field_path="usedFor")

    def test_remove_property(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_properties = current_container.properties.copy()
        del new_properties[TEXT_PROPERTY_ID]
        new_container = current_container.model_copy(update={"properties": new_properties})

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{TEXT_PROPERTY_ID}",
            expect_silent_ignore=True,
            neat_override_breaking_changes=True,
        )

    def test_add_property(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_property_id = "newProperty"
        new_property = ContainerPropertyDefinition(
            type=TextProperty(max_text_size=50, collation="ucs_basic", list=False),
            autoIncrement=False,
            immutable=False,
            nullable=True,
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, new_property_id: new_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{new_property_id}",
        )


class TestContainerPropertyDiffer:
    def test_diff_property_name(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True, update={"name": "Updated Text Property"}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{TEXT_PROPERTY_ID}.name",
        )

    def test_diff_property_description(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True, update={"description": "Updated description"}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{TEXT_PROPERTY_ID}.description",
        )

    def test_diff_property_immutable(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True, update={"immutable": True}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{TEXT_PROPERTY_ID}.immutable",
        )

    def test_diff_property_nullable(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True, update={"nullable": False}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{TEXT_PROPERTY_ID}.nullable",
            neat_override_breaking_changes=True,
        )

    def test_diff_property_auto_increment(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_int_property = current_container.properties[LISTABLE_INT_PROPERTY_ID].model_copy(
            deep=True, update={"auto_increment": True}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, LISTABLE_INT_PROPERTY_ID: new_int_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{LISTABLE_INT_PROPERTY_ID}.autoIncrement",
            expect_500=True,
            in_error_message="Internal server error",
        )

    def test_diff_property_default_value(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True, update={"default_value": "updated default"}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{TEXT_PROPERTY_ID}.defaultValue",
        )

    def test_diff_listable_property_list_false(
        self, current_container: ContainerRequest, neat_client: NeatClient
    ) -> None:
        new_int_property = current_container.properties[LISTABLE_BOOL_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": current_container.properties[LISTABLE_BOOL_PROPERTY_ID].type.model_copy(update={"list": False})
            },
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, LISTABLE_BOOL_PROPERTY_ID: new_int_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{LISTABLE_BOOL_PROPERTY_ID}.type.list",
            # The API considers the list as a type change and not a field change
            in_error_message="type",
        )

    def test_diff_listable_property_list_size_increase(
        self, current_container: ContainerRequest, neat_client: NeatClient
    ) -> None:
        new_int_property = current_container.properties[LISTABLE_INT_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": current_container.properties[LISTABLE_INT_PROPERTY_ID].type.model_copy(
                    update={"max_list_size": 20}
                )
            },
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, LISTABLE_INT_PROPERTY_ID: new_int_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{LISTABLE_INT_PROPERTY_ID}.type.maxListSize",
        )

    def test_diff_listable_property_list_size_decrease(
        self, current_container: ContainerRequest, neat_client: NeatClient
    ) -> None:
        new_int_property = current_container.properties[LISTABLE_INT_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": current_container.properties[LISTABLE_INT_PROPERTY_ID].type.model_copy(
                    update={"max_list_size": 5}
                )
            },
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, LISTABLE_INT_PROPERTY_ID: new_int_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{LISTABLE_INT_PROPERTY_ID}.type.maxListSize",
            neat_override_breaking_changes=True,
        )

    def test_diff_float_property_remove_unit(
        self, current_container: ContainerRequest, neat_client: NeatClient
    ) -> None:
        new_float_property = current_container.properties[FLOAT_PROPERTY_ID].model_copy(
            deep=True,
            update={"type": current_container.properties[FLOAT_PROPERTY_ID].type.model_copy(update={"unit": None})},
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, FLOAT_PROPERTY_ID: new_float_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{FLOAT_PROPERTY_ID}.type.unit",
            neat_override_breaking_changes=False,
            expect_silent_ignore=True,
        )

    def test_diff_float_property_change_source_unit(
        self, current_container: ContainerRequest, neat_client: NeatClient
    ) -> None:
        float_property = cast(Float32Property, current_container.properties[FLOAT_PROPERTY_ID].type)
        if float_property.unit is None:
            raise AssertionError(
                "The test container's float property should have a unit configured, but it was missing. "
                "The test setup may have changed or the API may be returning different default values."
            )
        new_float_property = current_container.properties[FLOAT_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": float_property.model_copy(
                    update={"unit": float_property.unit.model_copy(update={"source_unit": "cm"})}
                )
            },
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, FLOAT_PROPERTY_ID: new_float_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{FLOAT_PROPERTY_ID}.type.unit.sourceUnit",
        )

    def test_diff_float_property_change_unit_external_id(
        self, current_container: ContainerRequest, neat_client: NeatClient
    ) -> None:
        float_property = cast(Float32Property, current_container.properties[FLOAT_PROPERTY_ID].type)
        if float_property.unit is None:
            raise AssertionError(
                "The test container's float property should have a unit configured, but it was missing. "
                "The test setup may have changed or the API may be returning different default values."
            )
        new_float_property = current_container.properties[FLOAT_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": float_property.model_copy(
                    update={"unit": float_property.unit.model_copy(update={"external_id": "length:centim"})}
                )
            },
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, FLOAT_PROPERTY_ID: new_float_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{FLOAT_PROPERTY_ID}.type.unit.externalId",
        )

    def test_diff_text_property_collation(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True,
            update={"type": current_container.properties[TEXT_PROPERTY_ID].type.model_copy(update={"collation": "en"})},
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{TEXT_PROPERTY_ID}.type.collation",
            expect_500=True,
            in_error_message="Internal server error",
        )

    def test_diff_text_property_max_text_size_increase(
        self, current_container: ContainerRequest, neat_client: NeatClient
    ) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": current_container.properties[TEXT_PROPERTY_ID].type.model_copy(update={"max_text_size": 200})
            },
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{TEXT_PROPERTY_ID}.type.maxTextSize",
        )

    def test_diff_text_property_max_text_size_decrease(
        self, current_container: ContainerRequest, neat_client: NeatClient
    ) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": current_container.properties[TEXT_PROPERTY_ID].type.model_copy(update={"max_text_size": 50})
            },
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{TEXT_PROPERTY_ID}.type.maxTextSize",
        )

    def test_diff_enum_property_update_unknow(
        self, current_container: ContainerRequest, neat_client: NeatClient
    ) -> None:
        new_enum_property = current_container.properties[ENUM_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": current_container.properties[ENUM_PROPERTY_ID].type.model_copy(
                    update={"unknown_value": "toModify"}
                )
            },
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, ENUM_PROPERTY_ID: new_enum_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{ENUM_PROPERTY_ID}.type.unknownValue",
        )

    def test_diff_enum_property_remove(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        enum_property = cast(EnumProperty, current_container.properties[ENUM_PROPERTY_ID].type)
        new_values = enum_property.values.copy()
        del new_values["toRemove"]
        new_enum_property = current_container.properties[ENUM_PROPERTY_ID].model_copy(
            deep=True,
            update={"type": enum_property.model_copy(update={"values": new_values})},
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, ENUM_PROPERTY_ID: new_enum_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{ENUM_PROPERTY_ID}.type.values.toRemove",
            neat_override_breaking_changes=True,
            expect_silent_ignore=True,
        )

    def test_diff_enum_property_modify(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        enum_property = cast(EnumProperty, current_container.properties[ENUM_PROPERTY_ID].type)
        new_values = enum_property.values.copy()
        new_values["toModify"] = EnumValue(description="Updated description")
        new_enum_property = current_container.properties[ENUM_PROPERTY_ID].model_copy(
            deep=True,
            update={"type": enum_property.model_copy(update={"values": new_values})},
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, ENUM_PROPERTY_ID: new_enum_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{ENUM_PROPERTY_ID}.type.values.toModify.description",
        )

    def test_diff_enum_property_add(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        enum_property = cast(EnumProperty, current_container.properties[ENUM_PROPERTY_ID].type)
        new_values = enum_property.values.copy()
        new_values["toAdd"] = EnumValue(description="New enum value")
        new_enum_property = current_container.properties[ENUM_PROPERTY_ID].model_copy(
            deep=True,
            update={"type": enum_property.model_copy(update={"values": new_values})},
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, ENUM_PROPERTY_ID: new_enum_property}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"properties.{ENUM_PROPERTY_ID}.type.values.toAdd",
        )


class TestContainerConstraintDiffer:
    def test_change_constraint_type(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        if current_container.constraints is None:
            raise AssertionError(
                "The test container should have constraints configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
        new_constraint = RequiresConstraintDefinition(
            require=ContainerReference(space="cdf_cdm", external_id="CogniteAsset")
        )
        new_container = current_container.model_copy(
            update={"constraints": {**current_container.constraints, UNIQUENESS_CONSTRAINT_ID: new_constraint}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"constraints.{UNIQUENESS_CONSTRAINT_ID}.constraintType",
            in_error_message=UNIQUENESS_CONSTRAINT_ID,
        )

    def test_change_constraint_properties(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        if current_container.constraints is None:
            raise AssertionError(
                "The test container should have constraints configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
        uniqueness_constraint = cast(
            UniquenessConstraintDefinition, current_container.constraints[UNIQUENESS_CONSTRAINT_ID]
        )
        new_constraint = uniqueness_constraint.model_copy(
            deep=True, update={"properties": [TEXT_PROPERTY_ID, FLOAT_PROPERTY_ID]}
        )
        new_container = current_container.model_copy(
            update={"constraints": {**current_container.constraints, UNIQUENESS_CONSTRAINT_ID: new_constraint}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"constraints.{UNIQUENESS_CONSTRAINT_ID}.properties",
            in_error_message=UNIQUENESS_CONSTRAINT_ID,
        )

    def test_change_constraint_by_space(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        if current_container.constraints is None:
            raise AssertionError(
                "The test container should have constraints configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
        uniqueness_constraint = cast(
            UniquenessConstraintDefinition, current_container.constraints[UNIQUENESS_CONSTRAINT_ID]
        )
        new_constraint = uniqueness_constraint.model_copy(deep=True, update={"by_space": False})
        new_container = current_container.model_copy(
            update={"constraints": {**current_container.constraints, UNIQUENESS_CONSTRAINT_ID: new_constraint}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"constraints.{UNIQUENESS_CONSTRAINT_ID}.bySpace",
            in_error_message=UNIQUENESS_CONSTRAINT_ID,
        )

    def test_change_constraint_require(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        if current_container.constraints is None:
            raise AssertionError(
                "The test container should have constraints configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
        requires_constraint = cast(RequiresConstraintDefinition, current_container.constraints[REQUIRES_CONSTRAINT_ID])
        new_constraint = requires_constraint.model_copy(
            deep=True,
            update={"require": ContainerReference(space="cdf_cdm", external_id="CogniteAsset")},
        )
        new_container = current_container.model_copy(
            update={"constraints": {**current_container.constraints, REQUIRES_CONSTRAINT_ID: new_constraint}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"constraints.{REQUIRES_CONSTRAINT_ID}.require",
            in_error_message=REQUIRES_CONSTRAINT_ID,
        )


class TestContainerIndexDiffer:
    def test_change_index_type(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        if current_container.indexes is None:
            raise AssertionError(
                "The test container should have indexes configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
        new_index = InvertedIndex(properties=[TEXT_PROPERTY_ID])
        new_container = current_container.model_copy(
            update={"indexes": {**current_container.indexes, BTREE_INDEX_ID: new_index}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"indexes.{BTREE_INDEX_ID}.indexType",
            in_error_message=BTREE_INDEX_ID,
        )

    def test_change_index_properties(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        if current_container.indexes is None:
            raise AssertionError(
                "The test container should have indexes configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
        btree_index = cast(BtreeIndex, current_container.indexes[BTREE_INDEX_ID])
        new_index = btree_index.model_copy(deep=True, update={"properties": [TEXT_PROPERTY_ID, FLOAT_PROPERTY_ID]})
        new_container = current_container.model_copy(
            update={"indexes": {**current_container.indexes, BTREE_INDEX_ID: new_index}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"indexes.{BTREE_INDEX_ID}.properties",
            in_error_message=BTREE_INDEX_ID,
        )

    def test_change_btree_index_by_space(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        if current_container.indexes is None:
            raise AssertionError(
                "The test container should have indexes configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
        btree_index = cast(BtreeIndex, current_container.indexes[BTREE_INDEX_ID])
        new_index = btree_index.model_copy(deep=True, update={"by_space": False})
        new_container = current_container.model_copy(
            update={"indexes": {**current_container.indexes, BTREE_INDEX_ID: new_index}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"indexes.{BTREE_INDEX_ID}.bySpace",
            in_error_message=BTREE_INDEX_ID,
        )

    def test_change_btree_index_cursorable(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        if current_container.indexes is None:
            raise AssertionError(
                "The test container should have indexes configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
        btree_index = cast(BtreeIndex, current_container.indexes[BTREE_INDEX_ID])
        new_index = btree_index.model_copy(deep=True, update={"cursorable": False})
        new_container = current_container.model_copy(
            update={"indexes": {**current_container.indexes, BTREE_INDEX_ID: new_index}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"indexes.{BTREE_INDEX_ID}.cursorable",
            in_error_message=BTREE_INDEX_ID,
        )

    def test_adding_index(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_index_id = "newIndex"
        new_index = BtreeIndex(properties=[FLOAT_PROPERTY_ID], bySpace=False, cursorable=False)
        # Happy mypy, we know indexes is not None since there are existing indexes
        assert current_container.indexes is not None
        new_container = current_container.model_copy(
            update={"indexes": {**current_container.indexes, new_index_id: new_index}}
        )

        assert_change(
            ContainerDiffer(),
            current_container,
            new_container,
            neat_client.containers,
            field_path=f"indexes.{new_index_id}",
        )
