from collections.abc import Iterable
from uuid import uuid4

import pytest

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer._differ_data_model import DataModelDiffer
from cognite.neat._data_model.deployer.data_classes import (
    humanize_changes,
)
from cognite.neat._data_model.models.dms import (
    DataModelRequest,
    SpaceResponse,
    ViewReference,
)

from .utils import assert_allowed_change, assert_change


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

        assert_allowed_change(new_data_model, neat_client.data_models, "no changes", expect_silent_ignore=False)

    def test_diff_add_view(self, current_data_model: DataModelRequest, neat_client: NeatClient) -> None:
        new_data_model = current_data_model.model_copy(deep=True)
        if new_data_model.views is None:
            raise AssertionError(
                "The test data model should have views configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
        new_data_model.views.append(ViewReference(space="cdf_cdm", external_id="CogniteSourceSystem", version="v1"))

        assert_change(
            DataModelDiffer(),
            current_data_model,
            new_data_model,
            neat_client.data_models,
            field_path="views",
        )

    def test_diff_remove_view(self, current_data_model: DataModelRequest, neat_client: NeatClient) -> None:
        new_data_model = current_data_model.model_copy(deep=True)
        if new_data_model.views is None or len(new_data_model.views) == 0:
            raise AssertionError(
                "The test data model should have views configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
        new_data_model.views.pop(0)

        assert_change(
            DataModelDiffer(),
            current_data_model,
            new_data_model,
            neat_client.data_models,
            field_path="views",
            neat_override_breaking_changes=True,
            expect_silent_ignore=True,
        )
