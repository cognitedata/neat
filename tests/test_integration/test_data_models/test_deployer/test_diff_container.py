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
    ContainerPropertyDefinition,
    ContainerRequest,
    EnumProperty,
    EnumValue,
    Float32Property,
    Int32Property,
    SpaceResponse,
    TextProperty,
)
from cognite.neat._data_model.models.dms._data_types import Unit
from cognite.neat._exceptions import CDFAPIException
from cognite.neat._utils.http_client import FailedResponse

TEXT_PROPERTY_ID = "textProperty"
LISTABLE_INT_PROPERTY_ID = "listableProperty"
FLOAT_PROPERTY_ID = "floatProperty"
ENUM_PROPERTY_ID = "enumProperty"


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
                auto_increment=False,
                nullable=False,
            ),
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

    def test_remove_property(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_properties = current_container.properties.copy()
        del new_properties[TEXT_PROPERTY_ID]
        new_container = current_container.model_copy(update={"properties": new_properties})

        assert_change(current_container, new_container, neat_client, field_path=f"properties.{TEXT_PROPERTY_ID}")

    def test_add_property(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_property_id = "newProperty"
        new_property = ContainerPropertyDefinition(type=TextProperty(max_text_size=50))
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
            current_container, new_container, neat_client, field_path=f"properties.{TEXT_PROPERTY_ID}.nullable"
        )

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
        new_int_property = current_container.properties[LISTABLE_INT_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": current_container.properties[LISTABLE_INT_PROPERTY_ID].type.model_copy(update={"list": False})
            },
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, LISTABLE_INT_PROPERTY_ID: new_int_property}}
        )

        assert_change(
            current_container, new_container, neat_client, field_path=f"properties.{LISTABLE_INT_PROPERTY_ID}.type.list"
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
            current_container, new_container, neat_client, field_path=f"properties.{FLOAT_PROPERTY_ID}.type.unit"
        )

    def test_diff_float_property_change_source_unit(
        self, current_container: ContainerRequest, neat_client: NeatClient
    ) -> None:
        new_float_property = current_container.properties[FLOAT_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": current_container.properties[FLOAT_PROPERTY_ID].type.model_copy(
                    update={
                        "unit": current_container.properties[FLOAT_PROPERTY_ID].type.unit.model_copy(
                            update={"source_unit": "cm"}
                        )
                    }
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
        new_float_property = current_container.properties[FLOAT_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": current_container.properties[FLOAT_PROPERTY_ID].type.model_copy(
                    update={
                        "unit": current_container.properties[FLOAT_PROPERTY_ID].type.unit.model_copy(
                            update={"external_id": "length:cm"}
                        )
                    }
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

    def test_diff_enum_property_remove(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_values = current_container.properties[ENUM_PROPERTY_ID].type.values.copy()
        del new_values["toRemove"]
        new_enum_property = current_container.properties[ENUM_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": current_container.properties[ENUM_PROPERTY_ID].type.model_copy(update={"values": new_values})
            },
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, ENUM_PROPERTY_ID: new_enum_property}}
        )

        assert_change(
            current_container, new_container, neat_client, field_path=f"properties.{ENUM_PROPERTY_ID}.type.values"
        )

    def test_diff_enum_property_modify(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_values = current_container.properties[ENUM_PROPERTY_ID].type.values.copy()
        new_values["toModify"] = EnumValue(description="Updated description")
        new_enum_property = current_container.properties[ENUM_PROPERTY_ID].model_copy(
            deep=True,
            update={
                "type": current_container.properties[ENUM_PROPERTY_ID].type.model_copy(update={"values": new_values})
            },
        )
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, ENUM_PROPERTY_ID: new_enum_property}}
        )

        assert_change(
            current_container, new_container, neat_client, field_path=f"properties.{ENUM_PROPERTY_ID}.type.values"
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
            current_container, new_container, neat_client, field_path=f"properties.{ENUM_PROPERTY_ID}.type.values"
        )


def assert_change(
    current_container: ContainerRequest,
    new_container: ContainerRequest,
    neat_client: NeatClient,
    field_path: str,
) -> None:
    diffs = ContainerDiffer().diff(current_container, new_container)
    assert len(diffs) == 1
    diff = diffs[0]
    while isinstance(diff, FieldChanges):
        assert len(diff.changes) == 1
        diff = diff.changes[0]

    assert diff.field_path == field_path
    if diff.severity == SeverityType.BREAKING:
        field_name = field_path.split(".", maxsplit=1)[-1]
        assert_breaking_change(new_container, neat_client, field_name)
    else:
        # Both WARNING and SAFE are allowed changes
        assert_allowed_change(new_container, neat_client)


def assert_breaking_change(new_container: ContainerRequest, neat_client: NeatClient, field_name: str) -> None:
    with pytest.raises(CDFAPIException) as exc_info:
        _ = neat_client.containers.apply([new_container])

    responses = exc_info.value.messages
    assert len(responses) == 1
    response = responses[0]
    assert isinstance(response, FailedResponse)
    assert response.error.code == 400, (
        f"Expected HTTP 400 Bad Request for breaking change, got {response.error.code} with {response.error.message}"
    )
    assert field_name in response.error.message


def assert_allowed_change(new_container: ContainerRequest, neat_client: NeatClient) -> None:
    updated_container = neat_client.containers.apply([new_container])
    assert len(updated_container) == 1
    assert updated_container[0].as_request().model_dump() == new_container.model_dump(), (
        "Container after update does not match the desired state."
    )
