from collections.abc import Iterable
from uuid import uuid4

import pytest

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer._differ_data_model import DataModelDiffer
from cognite.neat._data_model.deployer.data_classes import (
    SeverityType,
    get_primitive_changes,
    humanize_changes,
)
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
        if len(created) != 1:
            raise AssertionError("Failed to set up data model for testing how the data model API reacts to changes.")
        created_data_model = created[0]
        yield created_data_model.as_request()
    finally:
        neat_client.data_models.delete([data_model.as_reference()])


class TestDataModelDiffer:
    def test_diff_no_changes(self, current_data_model: DataModelRequest, neat_client: NeatClient) -> None:
        new_data_model = current_data_model.model_copy(deep=True)
        diffs = DataModelDiffer().diff(current_data_model, new_data_model)
        if len(diffs) != 0:
            raise AssertionError(
                "Updating a data model without changes should yield no diffs, "
                f"but {len(diffs)} differences were detected.: {humanize_changes(diffs)}"
            )

        assert_allowed_change(new_data_model, neat_client, "no changes")

    def test_diff_add_view(self, current_data_model: DataModelRequest, neat_client: NeatClient) -> None:
        new_data_model = current_data_model.model_copy(deep=True)
        if new_data_model.views is None:
            raise AssertionError(
                "The test data model should have views configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
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
        if new_data_model.views is None or len(new_data_model.views) == 0:
            raise AssertionError(
                "The test data model should have views configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
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
    model_diffs = DataModelDiffer().diff(current_data_model, new_data_model)
    diffs = get_primitive_changes(model_diffs)
    if len(diffs) == 0:
        raise AssertionError(f"Updating a data model failed to change {field_path!r}. No changes were detected.")
    elif len(diffs) > 1:
        raise AssertionError(
            f"Updating a data model changed {field_path!r}, expected exactly one change,"
            f" but multiple changes were detected. "
            f"Changes detected:\n{humanize_changes(diffs)}"
        )
    diff = diffs[0]

    if field_path != diff.field_path:
        raise AssertionError(
            f"Updated a data model expected to change field '{field_path}', but the detected change was on "
            f"'{diff.field_path}'."
        )
    if diff.severity == SeverityType.BREAKING:
        field_name = field_path.rsplit(".", maxsplit=1)[-1]
        assert_breaking_change(new_data_model, neat_client, field_name)
    else:
        # Both WARNING and SAFE are allowed changes
        assert_allowed_change(new_data_model, neat_client, field_path)


def assert_breaking_change(new_data_model: DataModelRequest, neat_client: NeatClient, field_name: str) -> None:
    try:
        _ = neat_client.data_models.apply([new_data_model])
        raise AssertionError(
            f"Updating a data model with a breaking change to field '{field_name}' should fail, but it succeeded."
        )
    except CDFAPIException as exc_info:
        responses = exc_info.messages
        if len(responses) != 1:
            raise AssertionError(
                f"The API response should contain exactly one response when rejecting a breaking data model change, "
                f"but got {len(responses)} responses. The field changed was '{field_name}'."
            ) from None
        response = responses[0]
        if not isinstance(response, FailedResponse):
            raise AssertionError(
                f"The API response should be a FailedResponse when rejecting a breaking data model change, "
                f"but got {type(response).__name__}: {response!s}. The field changed was '{field_name}'."
            ) from None
        if response.error.code != 400:
            raise AssertionError(
                f"Expected HTTP 400 Bad Request for breaking data model change, got {response.error.code} with "
                f"message: {response.error.message}. The field changed was '{field_name}'."
            ) from None
        # The API considers the type change if the list property is changed
        in_error_message = "type" if field_name == "list" else field_name
        if in_error_message not in response.error.message:
            raise AssertionError(
                f"The error message for breaking data model change should mention '{in_error_message}', "
                f"but got: {response.error.message}. The field changed was '{field_name}'."
            ) from None


def assert_allowed_change(new_data_model: DataModelRequest, neat_client: NeatClient, field_name: str) -> None:
    updated_data_model = neat_client.data_models.apply([new_data_model])
    if len(updated_data_model) != 1:
        raise AssertionError(
            f"Updating a data model with an allowed change should succeed and return exactly one data model, "
            f"but got {len(updated_data_model)} data models. The field changed was '{field_name}'."
        )
    actual_dump = updated_data_model[0].as_request().model_dump(by_alias=True, exclude_none=False)
    expected_dump = new_data_model.model_dump(by_alias=True, exclude_none=False)
    if actual_dump != expected_dump:
        raise AssertionError(
            f"Failed to update the data model field '{field_name}', the change was silently ignored by the API."
        )
