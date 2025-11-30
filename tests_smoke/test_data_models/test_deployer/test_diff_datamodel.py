from collections.abc import Iterable
from uuid import uuid4

import pytest

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer._differ_data_model import DataModelDiffer
from cognite.neat._data_model.deployer.data_classes import FieldChanges, SeverityType
from cognite.neat._data_model.models.dms import (
    DataModelRequest,
    SpaceResponse,
    ViewReference,
)
from cognite.neat._exceptions import CDFAPIException
from cognite.neat._utils.http_client import FailedResponse


@pytest.fixture(scope="function")
def current_data_model(neat_test_space: SpaceResponse, neat_client: NeatClient) -> Iterable[DataModelRequest]:
    """This is the data model in CDF before changes."""
    # We use a random ID to avoid conflicts between tests
    random_id = str(uuid4()).replace("-", "_")
    data_model = DataModelRequest(
        space=neat_test_space.space,
        externalId=f"test_datamodel_{random_id}",
        version="v1",
        name="Initial name",
        description="Initial description",
        views=[
            ViewReference(space="cdf_cdm", external_id="CogniteDescribable", version="v1"),
            ViewReference(space="cdf_cdm", external_id="CogniteSchedulable", version="v1"),
        ],
    )
    try:
        created = neat_client.data_models.apply([data_model])
        assert len(created) == 1
        created_data_model = created[0]
        yield created_data_model.as_request()
    finally:
        neat_client.data_models.delete([data_model.as_reference()])


class TestDataModelDiffer:
    def test_diff_no_changes(self, current_data_model: DataModelRequest, neat_client: NeatClient) -> None:
        new_data_model = current_data_model.model_copy(deep=True)
        diffs = DataModelDiffer().diff(current_data_model, new_data_model)
        assert len(diffs) == 0

        assert_allowed_change(new_data_model, neat_client)

    def test_diff_add_view(self, current_data_model: DataModelRequest, neat_client: NeatClient) -> None:
        new_data_model = current_data_model.model_copy(deep=True)
        assert new_data_model.views is not None
        new_data_model.views.append(ViewReference(space="cdf_cdm", external_id="CogniteSourceSystem", version="v1"))

        assert_change(
            current_data_model,
            new_data_model,
            neat_client,
            field_path="views",
        )

    @pytest.mark.skip(reason="API returns 200 but does not add the view. What to do?")
    def test_diff_remove_view(self, current_data_model: DataModelRequest, neat_client: NeatClient) -> None:
        new_data_model = current_data_model.model_copy(deep=True)
        assert new_data_model.views is not None and len(new_data_model.views) > 0, "Precondition failed."
        new_data_model.views.pop(0)

        assert_change(
            current_data_model,
            new_data_model,
            neat_client,
            field_path="views",
        )


def assert_change(
    current_data_model: DataModelRequest,
    new_data_model: DataModelRequest,
    neat_client: NeatClient,
    field_path: str,
) -> None:
    diffs = DataModelDiffer().diff(current_data_model, new_data_model)
    assert len(diffs) == 1
    diff = diffs[0]
    while isinstance(diff, FieldChanges):
        assert len(diff.changes) == 1
        diff = diff.changes[0]

    assert field_path == diff.field_path, f"Expected diff on field path {field_path}, got {diff.field_path}"
    if diff.severity == SeverityType.BREAKING:
        field_name = field_path.rsplit(".", maxsplit=1)[-1]
        assert_breaking_change(new_data_model, neat_client, field_name)
    else:
        # Both WARNING and SAFE are allowed changes
        assert_allowed_change(new_data_model, neat_client)


def assert_breaking_change(new_data_model: DataModelRequest, neat_client: NeatClient, field_name: str) -> None:
    with pytest.raises(CDFAPIException) as exc_info:
        _ = neat_client.data_models.apply([new_data_model])

    responses = exc_info.value.messages
    assert len(responses) == 1
    response = responses[0]
    assert isinstance(response, FailedResponse)
    assert response.error.code == 400, (
        f"Expected HTTP 400 Bad Request for breaking change, got {response.error.code} with {response.error.message}"
    )
    # The API considers the type change if the list property is changed
    field_name = "type" if field_name == "list" else field_name
    assert field_name in response.error.message


def assert_allowed_change(new_data_model: DataModelRequest, neat_client: NeatClient) -> None:
    updated_data_model = neat_client.data_models.apply([new_data_model])
    assert len(updated_data_model) == 1
    assert updated_data_model[0].as_request().model_dump(
        by_alias=True, exclude_none=False
    ) == new_data_model.model_dump(by_alias=True, exclude_none=False), (
        "Data Model after update does not match the desired state."
    )
