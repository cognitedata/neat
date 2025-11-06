from collections.abc import Iterable
from typing import cast
from uuid import uuid4

import pytest

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer._differ_container import ContainerDiffer
from cognite.neat._data_model.deployer.data_classes import (
    FieldChanges,
    SeverityType,
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
        assert len(created) == 1
        created_container = created[0]
        yield created_container.as_request()
    finally:
        neat_client.containers.delete([container.as_reference()])


class TestContainerDiffer:
    def test_diff_no_changes(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_container = current_container.model_copy(deep=True)
        diffs = ContainerDiffer().diff(current_container, new_container)
        assert len(diffs) == 0

        assert_allowed_change(new_container, neat_client)

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

    @pytest.mark.skip(
        reason="API returns 200 and does the change. This can lead to properties with null in a"
        " non-nullable field. What should we do?"
    )
    def test_diff_property_nullable(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_text_property = current_container.properties[TEXT_PROPERTY_ID].model_copy(
            deep=True, update={"nullable": False}
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        assert_change(
            current_container, new_container, neat_client, field_path=f"properties.{TEXT_PROPERTY_ID}.nullable"
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

    @pytest.mark.skip(
        reason="API returns 200 and does the change. However, decreasing a list size can lead to "
        "data loss or an invalid state (more relations than the limit). What should we do?"
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
        assert float_property.unit is not None
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
        assert float_property.unit is not None
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
        assert current_container.constraints is not None
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
        assert current_container.constraints is not None
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
        assert current_container.constraints is not None
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
        assert current_container.constraints is not None
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
        assert current_container.indexes is not None
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
        assert current_container.indexes is not None
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
        assert current_container.indexes is not None
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
        assert current_container.indexes is not None
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
) -> None:
    diffs = ContainerDiffer().diff(current_container, new_container)
    assert len(diffs) == 1
    diff = diffs[0]
    while isinstance(diff, FieldChanges):
        assert len(diff.changes) == 1
        diff = diff.changes[0]

    assert field_path == diff.field_path, f"Expected diff on field path {field_path}, got {diff.field_path}"
    if diff.severity == SeverityType.BREAKING:
        if in_error_message is None:
            in_error_message = field_path.rsplit(".", maxsplit=1)[-1]
        assert_breaking_change(new_container, neat_client, in_error_message)
    else:
        # Both WARNING and SAFE are allowed changes
        assert_allowed_change(new_container, neat_client)


def assert_breaking_change(new_container: ContainerRequest, neat_client: NeatClient, in_error_message: str) -> None:
    with pytest.raises(CDFAPIException) as exc_info:
        _ = neat_client.containers.apply([new_container])

    responses = exc_info.value.messages
    assert len(responses) == 1
    response = responses[0]
    assert isinstance(response, FailedResponse)
    assert response.error.code == 400, (
        f"Expected HTTP 400 Bad Request for breaking change, got {response.error.code} with {response.error.message}"
    )
    # The API considers the type change if the list property is changed
    assert in_error_message in response.error.message


def assert_allowed_change(new_container: ContainerRequest, neat_client: NeatClient) -> None:
    updated_container = neat_client.containers.apply([new_container])
    assert len(updated_container) == 1
    assert updated_container[0].as_request().model_dump(by_alias=True, exclude_none=False) == new_container.model_dump(
        by_alias=True, exclude_none=False
    ), "Container after update does not match the desired state."
