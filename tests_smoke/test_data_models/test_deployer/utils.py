from cognite.neat._client.containers_api import ContainersAPI
from cognite.neat._client.data_model_api import DataModelsAPI
from cognite.neat._client.views_api import ViewsAPI
from cognite.neat._data_model.deployer._differ import ItemDiffer
from cognite.neat._data_model.deployer.data_classes import (
    SeverityType,
    get_primitive_changes,
    humanize_changes,
)
from cognite.neat._data_model.models.dms import Resource, T_Resource
from cognite.neat._exceptions import CDFAPIException
from cognite.neat._utils.http_client import FailedResponse


def assert_change(
    differ: ItemDiffer[T_Resource],
    current_resource: T_Resource,
    new_resource: T_Resource,
    api: ViewsAPI | ContainersAPI | DataModelsAPI,
    field_path: str,
    in_error_message: str | None = None,
    neat_override_breaking_changes: bool = False,
    expect_silent_ignore: bool = False,
    expect_500: bool = False,
) -> None:
    """Asserts that the change between current_resource and new_resource is detected on the given field_path.

    If the change is breaking, it asserts that applying the new_resource raises an error containing in_error_message.
    If the change is allowed, it asserts that applying the new_resource succeeds.

    Args:
        differ (ItemDiffer): The differ to use for detecting changes.
        current_resource (Resource): The current container/view/data model state.
        new_resource (Resource): The new container/view/data model state with the change.
        api: ViewsAPI | ContainersAPI | DataModelsAPI: The API client to use for applying the changes.
        field_path (str): The expected field path where the change occurs.
        in_error_message (str | None): The substring expected in the error message for breaking changes
            (defaults to the last part of the field_path).
        neat_override_breaking_changes (bool): If True, all changes are treated as allowed, even if the severity is
            breaking. This is used for changes that we in the Neat team have decided to consider BREAKING, even
            though they are not technically breaking from a CDF API perspective.
        expect_silent_ignore (bool): If True, the change is expected to be silently ignored by the API.
        expect_500 (bool): If True, the change is expected to cause a 500 Internal Server Error from the API.

    """
    resource_name = type(current_resource).__name__.removesuffix("Request")
    resource_diffs = differ.diff(current_resource, new_resource)
    diffs = get_primitive_changes(resource_diffs)
    if len(diffs) == 0:
        raise AssertionError(f"Updating a {resource_name} failed to change {field_path!r}. No changes were detected.")
    elif len(diffs) > 1:
        raise AssertionError(
            f"Updating a {resource_name} changed {field_path!r}, expected exactly one change,"
            f" but multiple changes were detected. "
            f"Changes detected:\n{humanize_changes(diffs)}"
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
            f"Updated a {resource_name} expected to change field '{field_path}', but the detected change was on "
            f"{diff.field_path}'. "
        )

    if (diff.severity == SeverityType.BREAKING and not neat_override_breaking_changes) or expect_500:
        if in_error_message is None:
            in_error_message = field_path.rsplit(".", maxsplit=1)[-1]
        assert_breaking_change(new_resource, api, in_error_message, field_path, expect_500)
    else:
        # Both WARNING and SAFE are allowed changes
        assert_allowed_change(new_resource, api, field_path, expect_silent_ignore)


def assert_breaking_change(
    new_resource: Resource,
    api: ViewsAPI | ContainersAPI | DataModelsAPI,
    in_error_message: str,
    field_path: str,
    expect_500: bool = False,
) -> None:
    resource_name = type(new_resource).__name__.removesuffix("Request")
    try:
        _ = api.apply([new_resource])  # type: ignore[list-item]
        raise AssertionError(
            f"Updating a {resource_name} with a breaking change to field '{field_path}' should fail, but it succeeded."
        )
    except CDFAPIException as exc_info:
        responses = exc_info.messages
        if len(responses) != 1:
            raise AssertionError(
                "The API response should contain exactly one response when "
                f"rejecting a breaking {resource_name} change, "
                f"but got {len(responses)} responses. The field attempted changed was '{field_path}'. "
            ) from None
        response = responses[0]
        if not isinstance(response, FailedResponse):
            raise AssertionError(
                f"The API response should be a FailedResponse when rejecting a breaking {resource_name} change, "
                f"but got {type(response).__name__}: {response!s}. The field changed was '{field_path}'. "
            ) from None
        if response.error.code != 400 and not expect_500:
            raise AssertionError(
                f"Expected HTTP 400 Bad Request for breaking {resource_name} change, got {response.error.code} with "
                f"message: {response.error.message}. The field changed was '{field_path}'. "
            ) from None
        if response.error.code != 500 and expect_500:
            raise AssertionError(
                f"Expected HTTP 500 Internal Server Error for breaking {resource_name} change, "
                f"got {response.error.code} with "
                f"message: {response.error.message}. The field changed was '{field_path}'. "
            ) from None
        # The API considers the type change if the list property is changed
        if in_error_message not in response.error.message:
            raise AssertionError(
                f"The error message for breaking {resource_name} change should mention '{in_error_message}', "
                f"but got: {response.error.message}. The field changed was '{field_path}'. "
            ) from None


def assert_allowed_change(
    new_resource: Resource,
    api: DataModelsAPI | ViewsAPI | ContainersAPI,
    field_path: str,
    expect_silent_ignore: bool = False,
) -> None:
    resource_name = type(new_resource).__name__.removesuffix("Request")
    updated_resource = api.apply([new_resource])  # type: ignore[list-item]
    if len(updated_resource) != 1:
        raise AssertionError(
            f"Updating a {resource_name} with an allowed change should succeed and return exactly one {resource_name}, "
            f"but got {len(updated_resource)} {resource_name}s. The field changed was '{field_path}'. "
        )
    actual_dump = updated_resource[0].as_request().model_dump(by_alias=True, exclude_none=False)
    expected_dump = new_resource.model_dump(by_alias=True, exclude_none=False)
    if expect_silent_ignore:
        if actual_dump == expected_dump:
            raise AssertionError(
                f"Expected the change to field {field_path!r} for {resource_name} to be silently ignored "
                "by the API, but it was applied."
            )
    else:
        if actual_dump != expected_dump:
            raise AssertionError(
                f"Failed to the {resource_name} field {field_path!r}, the change was silently ignored by the API. "
            )
