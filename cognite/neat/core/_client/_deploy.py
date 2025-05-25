from collections.abc import Hashable
from typing import Literal, TypeAlias

from cognite.client.data_classes._base import CogniteResource, CogniteResourceList
from cognite.client.exceptions import CogniteAPIError

from ._api.crud import CrudAPI
from .data_classes.deploy_result import DeployResult, FailedRequest, ForcedResource

# Support overwrite?
ExistingResource: TypeAlias = Literal["skip", "fail", "update", "force", "recreate"]


def deploy(
    crud_api: CrudAPI,
    resources: CogniteResourceList,
    existing: ExistingResource,
    dry_run: bool = False,
    restore_on_failure: bool = False,
) -> DeployResult:
    """Deploy a resource or a sequence of resources to CDF.

    Args:
        crud_api: The CrudAPI instance to use for deployment.
        resources: The  resources to deploy.
        existing: How to handle existing resources. Options are "skip", "fail", "update", "force", and "recreate".
        dry_run: If True, only simulate the deployment without making any changes.
        restore_on_failure: If True, restore the resource if it fails to deploy. This is only applicable if
            `existing` is set to "update.

    ... note::

    - "fail": Raise an error if the resource already exists.
    - "skip": Skip the resource if it already exists.
    - "update": Update the resource if it already exists. This has different behavior depending
        on the resource type.
    - "force": Tries to update the resource, but if it fails, it will recreate the resource.
    - "recreate": Delete the existing resource and create a new one, regardless of whether it exists or not.

    """
    if restore_on_failure and not crud_api.support_restore_on_failure:
        raise ValueError(f"The {crud_api.list_cls.__name__} does not support restoring on failure. ")

    cdf_resources = crud_api.retrieve(crud_api.as_ids(resources))
    cdf_resource_by_id = {crud_api.as_id(resource): resource for resource in cdf_resources}
    local_by_id = {crud_api.as_id(resource): resource for resource in resources}

    result, to_create, to_delete, to_update = _prepare_api_calls(
        crud_api, local_by_id, cdf_resource_by_id, dry_run, existing
    )

    if existing == "fail" and result.existing:
        result.status = "failure"
        result.message = f"Cannot deploy {len(resources)} resources, {len(result.existing)} already exist."
        return result

    if dry_run:
        return result

    _api_calls(crud_api, to_create, to_delete, to_update, result, cdf_resource_by_id, existing == "force")

    if result.status == "failure" and restore_on_failure:
        raise NotImplementedError()
    return result


def _prepare_api_calls(
    crud_api: CrudAPI,
    local_by_id: dict[Hashable, CogniteResource],
    cdf_resource_by_id: dict[Hashable, CogniteResource],
    dry_run: bool,
    existing: ExistingResource,
) -> tuple[DeployResult, CogniteResourceList, list[Hashable], CogniteResourceList]:
    to_create, to_update, to_delete = (
        crud_api.list_cls([]),
        crud_api.list_cls([]),
        [],
    )
    result = DeployResult("dry-run" if dry_run else "success")
    for id_, local in local_by_id.items():
        cdf_resource = cdf_resource_by_id.get(id_)
        if cdf_resource is None:
            to_create.append(local)
            result.to_create.append(id_)
        elif existing == "skip":
            result.skipped.append(id_)
        elif existing == "fail":
            result.status = "failure"
            result.existing.append(id_)
        elif existing == "recreate":
            to_delete.append(id_)
            to_create.append(local)
            result.to_delete.append(id_)
            result.to_create.append(id_)
        elif diffs := crud_api.difference(local, cdf_resource):
            result.diffs.append(diffs)
            result.to_update.append(id_)
            if crud_api.support_merge:
                to_update.append(crud_api.merge(local, cdf_resource))
            else:
                to_update.append(local)
        else:
            result.unchanged.append(id_)
    return result, to_create, to_delete, to_update


def _api_calls(
    crud_api: CrudAPI,
    to_create: CogniteResourceList,
    to_delete: list[Hashable],
    to_update: CogniteResourceList,
    result: DeployResult,
    cdf_resource_by_id: dict[Hashable, CogniteResource],
    is_force_update: bool,
) -> None:
    if to_delete:
        try:
            deleted_ids = crud_api.delete(to_delete)
        except CogniteAPIError as e:
            result.status = "failure"
            result.message = f"Failed to delete {len(to_delete)} resources: {e!r}"
            result.failed_deleted.append(
                FailedRequest(
                    error_message=str(e),
                    status_code=e.code,
                    resource_ids=to_delete,
                )
            )
        else:
            result.deleted.extend(deleted_ids)

    if to_create and result.status != "failure":
        try:
            created = crud_api.create(to_create)
        except CogniteAPIError as e:
            result.status = "failure"
            result.message = f"Failed to create {len(to_create)} resources: {e!r}"
            result.failed_created.append(
                FailedRequest(
                    error_message=str(e),
                    status_code=e.code,
                    resource_ids=crud_api.as_ids(to_create),
                )
            )
        else:
            result.created.extend(crud_api.as_ids(created))

    if to_update and result.status != "failure":
        try:
            updated = crud_api.update(to_update)
        except CogniteAPIError as e1:
            if is_force_update:
                _force_update_calls(crud_api, to_update, cdf_resource_by_id, result, e1)
            else:
                result.status = "failure"
                result.message = f"Failed to update {len(to_update)} resources: {e1!r}"
                result.failed_updated.append(
                    FailedRequest(
                        error_message=str(e1),
                        status_code=e1.code,
                        resource_ids=crud_api.as_ids(to_update),
                    )
                )
        else:
            _update_results_with_update_response(crud_api, updated, cdf_resource_by_id, result)


def _force_update_calls(
    crud_api: CrudAPI,
    to_update: CogniteResourceList,
    cdf_resource_by_id: dict[Hashable, CogniteResource],
    result: DeployResult,
    error: CogniteAPIError,
) -> None:
    to_delete_ids = crud_api.as_ids(to_update)
    try:
        _ = crud_api.delete(to_delete_ids)
    except CogniteAPIError as e2:
        result.status = "failure"
        result.message = f"Failed to force update resources. The delete operation failed: {e2!r}"
        result.failed_deleted.append(
            FailedRequest(
                error_message=str(e2),
                status_code=e2.code,
                resource_ids=to_delete_ids,
            )
        )
        return
    try:
        created = crud_api.create(to_update)
    except CogniteAPIError as e3:
        result.status = "failure"
        result.message = f"Failed to force update resources. The create operation failed: {e3!r}"
        result.failed_created.append(
            FailedRequest(
                error_message=str(e3),
                status_code=e3.code,
                resource_ids=crud_api.as_ids(to_update),
            )
        )
        return
    result.forced.extend(
        [
            ForcedResource(
                resource_id=resource_id,
                reason=str(error),
            )
            for resource_id in crud_api.as_ids(created)
        ]
    )
    _update_results_with_update_response(crud_api, created, cdf_resource_by_id, result)


def _update_results_with_update_response(
    crud_api: CrudAPI,
    updated: CogniteResourceList,
    cdf_resource_by_id: dict[Hashable, CogniteResource],
    result: DeployResult,
) -> None:
    for resource in updated:
        id_ = crud_api.as_id(resource)
        previous = cdf_resource_by_id[id_]
        result.updated.append(crud_api.difference(resource, previous))
