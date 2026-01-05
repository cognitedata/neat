from collections.abc import Iterable
from typing import cast
from uuid import uuid4

import pytest

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer._differ_container import ContainerDiffer
from cognite.neat._data_model.deployer.data_classes import (
    SeverityType,
    get_primitive_changes,
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
from cognite.neat._exceptions import CDFAPIException
from cognite.neat._utils.http_client import FailedResponse

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

        assert_allowed_change(new_container, neat_client, "no changes")

    def test_diff_used_for(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_container = current_container.model_copy(deep=True, update={"used_for": "edge"})
        assert_change(current_container, new_container, neat_client, field_path="usedFor")

    @pytest.mark.skip(reason="API returns 200, while it silently ignores the change. What should we do?")
    def test_remove_property(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_properties = current_container.properties.copy()
        del new_properties[TEXT_PROPERTY_ID]
        new_container = current_container.model_copy(update={"properties": new_properties})

        assert_change(current_container, new_container, neat_client, field_path=f"properties.{TEXT_PROPERTY_ID}")

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

        assert_change(current_container, new_container, neat_client, field_path=f"properties.{new_property_id}")


class TestContainerPropertyDiffer:
    def test_diff_property_name(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True, update={"name": "Updated Text Property"}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(current_container, new_container, neat_client, field_path=f"properties.{TEXT_PROPERTY_ID}.name")

    def test_diff_property_description(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True, update={"description": "Updated description"}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            current_container, new_container, neat_client, field_path=f"properties.{TEXT_PROPERTY_ID}.description"
        )

    def test_diff_property_immutable(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True, update={"immutable": True}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            current_container, new_container, neat_client, field_path=f"properties.{TEXT_PROPERTY_ID}.immutable"
        )

    def test_diff_property_nullable(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True, update={"nullable": False}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            current_container,
            new_container,
            neat_client,
            field_path=f"properties.{TEXT_PROPERTY_ID}.nullable",
            neat_override_breaking_changes=True,
        )

    @pytest.mark.skip(reason="API returns 500; Internal server error. What should we do?")
    def test_diff_property_auto_increment(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_int_property = current_container.properties[LISTABLE_INT_PROPERTY_ID].model_copy(
            deep=True, update={"auto_increment": True}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, LISTABLE_INT_PROPERTY_ID: new_int_property}}
        )

        assert_change(
            current_container,
            new_container,
            neat_client,
            field_path=f"properties.{LISTABLE_INT_PROPERTY_ID}.autoIncrement",
        )

    def test_diff_property_default_value(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True, update={"default_value": "updated default"}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            current_container, new_container, neat_client, field_path=f"properties.{TEXT_PROPERTY_ID}.defaultValue"
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
            current_container,
            new_container,
            neat_client,
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
            current_container,
            new_container,
            neat_client,
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
            current_container,
            new_container,
            neat_client,
            field_path=f"properties.{LISTABLE_INT_PROPERTY_ID}.type.maxListSize",
            neat_override_breaking_changes=True,
        )

    @pytest.mark.skip(reason="API returns 200,but does not do the change. What should we do?")
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
            current_container, new_container, neat_client, field_path=f"properties.{FLOAT_PROPERTY_ID}.type.unit"
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
            current_container,
            new_container,
            neat_client,
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
            current_container,
            new_container,
            neat_client,
            field_path=f"properties.{FLOAT_PROPERTY_ID}.type.unit.externalId",
        )

    @pytest.mark.skip(reason="API returns 500; Internal server error. What should we do?")
    def test_diff_text_property_collation(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True,
            update={"type": current_container.properties[TEXT_PROPERTY_ID].type.model_copy(update={"collation": "en"})},
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            current_container, new_container, neat_client, field_path=f"properties.{TEXT_PROPERTY_ID}.type.collation"
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
            current_container, new_container, neat_client, field_path=f"properties.{TEXT_PROPERTY_ID}.type.maxTextSize"
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
            current_container, new_container, neat_client, field_path=f"properties.{TEXT_PROPERTY_ID}.type.maxTextSize"
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
            current_container, new_container, neat_client, field_path=f"properties.{ENUM_PROPERTY_ID}.type.unknownValue"
        )

    @pytest.mark.skip(reason="API returns 200, but silently skips the change. What should we do?")
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
            current_container,
            new_container,
            neat_client,
            field_path=f"properties.{ENUM_PROPERTY_ID}.type.values.toRemove",
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
            current_container,
            new_container,
            neat_client,
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
            current_container, new_container, neat_client, field_path=f"properties.{ENUM_PROPERTY_ID}.type.values.toAdd"
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
            current_container,
            new_container,
            neat_client,
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
            current_container,
            new_container,
            neat_client,
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
            current_container,
            new_container,
            neat_client,
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
            current_container,
            new_container,
            neat_client,
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
            current_container,
            new_container,
            neat_client,
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
            current_container,
            new_container,
            neat_client,
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
            current_container,
            new_container,
            neat_client,
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
            current_container,
            new_container,
            neat_client,
            field_path=f"indexes.{BTREE_INDEX_ID}.cursorable",
            in_error_message=BTREE_INDEX_ID,
        )


def assert_change(
    current_container: ContainerRequest,
    new_container: ContainerRequest,
    neat_client: NeatClient,
    field_path: str,
    in_error_message: str | None = None,
    neat_override_breaking_changes: bool = False,
) -> None:
    """Asserts that the change between current_container and new_container is detected on the given field_path.

    If the change is breaking, it asserts that applying the new_container raises an error containing in_error_message.
    If the change is allowed, it asserts that applying the new_container succeeds.

    Args:
        current_container (ContainerRequest): The current container state.
        new_container (ContainerRequest): The new container state with the change.
        neat_client (NeatClient): The NEAT client to use for applying changes.
        field_path (str): The expected field path where the change occurs.
        in_error_message (str | None): The substring expected in the error message for breaking changes
            (defaults to the last part of the field_path).
        neat_override_breaking_changes (bool): If True, all changes are treated as allowed, even if the severity is
            breaking. This is used for changes that we in the Neat team have decided to consider BREAKING, even
            though they are not technically breaking from a CDF API perspective.
    """
    container_diffs = ContainerDiffer().diff(current_container, new_container)
    diffs = get_primitive_changes(container_diffs)
    if len(diffs) == 0:
        raise AssertionError(f"Updating a container failed to change {field_path!r}. No changes were detected.")
    elif len(diffs) > 1:
        raise AssertionError(
            f"Updating a container changed {field_path!r}, expected exactly one change,"
            f" but multiple changes were detected. "
            f"Changes detected:\n{humanize_changes(container_diffs)}"
        )
    diff = diffs[0]

    if neat_override_breaking_changes:
        if diff.severity != SeverityType.BREAKING:
            raise AssertionError(
                f"The change to '{field_path}' should be classified as BREAKING by Neat's internal rules, "
                f"but it was classified as {diff.severity}. This indicates a change in how Neat classifies "
                "breaking changes has changed."
            )

    # Ensure that the diff is on the expected field path
    if field_path != diff.field_path:
        raise AssertionError(
            f"Updated a container expected to change field '{field_path}', but the detected change was on "
            f"{diff.field_path}'. "
        )

    if diff.severity == SeverityType.BREAKING and not neat_override_breaking_changes:
        if in_error_message is None:
            in_error_message = field_path.rsplit(".", maxsplit=1)[-1]
        assert_breaking_change(new_container, neat_client, in_error_message, field_path)
    else:
        # Both WARNING and SAFE are allowed changes
        assert_allowed_change(new_container, neat_client, field_path)


def assert_breaking_change(
    new_container: ContainerRequest, neat_client: NeatClient, in_error_message: str, field_path: str
) -> None:
    try:
        _ = neat_client.containers.apply([new_container])
        raise AssertionError(
            f"Updating a container with a breaking change to field '{field_path}' should fail, but it succeeded."
        )
    except CDFAPIException as exc_info:
        responses = exc_info.messages
        if len(responses) != 1:
            raise AssertionError(
                f"The API response should contain exactly one response when rejecting a breaking contaienr change, "
                f"but got {len(responses)} responses. The field changed was '{field_path}'. "
            ) from None
        response = responses[0]
        if not isinstance(response, FailedResponse):
            raise AssertionError(
                f"The API response should be a FailedResponse when rejecting a breaking container change, "
                f"but got {type(response).__name__}: {response!s}. The field changed was '{field_path}'. "
            ) from None
        if response.error.code != 400:
            raise AssertionError(
                f"Expected HTTP 400 Bad Request for breaking container change, got {response.error.code} with "
                f"message: {response.error.message}. The field changed was '{field_path}'. "
            ) from None
        # The API considers the type change if the list property is changed
        if in_error_message not in response.error.message:
            raise AssertionError(
                f"The error message for breaking container change should mention '{in_error_message}', "
                f"but got: {response.error.message}. The field changed was '{field_path}'. "
            ) from None


def assert_allowed_change(new_container: ContainerRequest, neat_client: NeatClient, field_path: str) -> None:
    updated_container = neat_client.containers.apply([new_container])
    if len(updated_container) != 1:
        raise AssertionError(
            f"Updating a container with an allowed change should succeed and return exactly one container, "
            f"but got {len(updated_container)} containers. The field changed was '{field_path}'. "
        )
    actual_dump = updated_container[0].as_request().model_dump(by_alias=True, exclude_none=False)
    expected_dump = new_container.model_dump(by_alias=True, exclude_none=False)
    if actual_dump != expected_dump:
        raise AssertionError(
            f"Failed to the container field {field_path!r}, the change was silently ignored by the API. "
        )
