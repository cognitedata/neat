from collections.abc import Iterable
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
    SpaceResponse,
    TextProperty,
)
from cognite.neat._exceptions import CDFAPIException
from cognite.neat._utils.http_client import FailedResponse

TEXT_PROPERTY_ID = "textProperty"


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
                auto_increment=False,
                default_value="default text",
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

        self.assert_allowed_change(new_container, neat_client)

    def test_diff_used_for(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        new_container = current_container.model_copy(deep=True, update={"used_for": "edge"})
        self.assert_change(current_container, new_container, neat_client, field_path="usedFor")

    def test_diff_property_name(self, current_container: ContainerRequest, neat_client: NeatClient) -> None:
        text_property = current_container.properties[TEXT_PROPERTY_ID]
        new_text_property = text_property.model_copy(deep=True, update={"name": "Updated Text Property"})
        new_container = current_container.model_copy(
            update={"properties": {**current_container.properties, TEXT_PROPERTY_ID: new_text_property}}
        )

        self.assert_change(
            current_container, new_container, neat_client, field_path=f"properties.{TEXT_PROPERTY_ID}.name"
        )

    @classmethod
    def assert_change(
        cls,
        current_container: ContainerRequest,
        new_container: ContainerRequest,
        neat_client: NeatClient,
        field_path: str,
    ) -> None:
        diffs = ContainerDiffer().diff(current_container, new_container)
        assert len(diffs) == 1
        diff = diffs[0]
        if isinstance(diff, FieldChanges):
            assert len(diff.changes) == 1
            diff = diff.changes[0]

        assert diff.field_path == field_path
        if diff.severity == SeverityType.BREAKING:
            field_name = field_path.split(".", maxsplit=1)[-1]
            cls.assert_breaking_change(new_container, neat_client, field_name)
        else:
            # Both WARNING and SAFE are allowed changes
            cls.assert_allowed_change(new_container, neat_client)

    @classmethod
    def assert_breaking_change(cls, new_container: ContainerRequest, neat_client: NeatClient, field_name: str) -> None:
        with pytest.raises(CDFAPIException) as exc_info:
            _ = neat_client.containers.apply([new_container])

        responses = exc_info.value.messages
        assert len(responses) == 1
        response = responses[0]
        assert isinstance(response, FailedResponse)
        assert response.error.code == 400
        assert field_name in response.error.message

    @classmethod
    def assert_allowed_change(cls, new_container: ContainerRequest, neat_client: NeatClient) -> None:
        updated_container = neat_client.containers.apply([new_container])
        assert len(updated_container) == 1
        assert updated_container[0].as_request().model_dump() == new_container.model_dump(), (
            "Container after update does not match the desired state."
        )
