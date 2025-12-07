import uuid
from typing import Any

from cognite.neat._data_model.deployer.data_classes import DeploymentResult

from ._changes import SerializedChanges
from ._statistics import DeploymentStatistics


def serialize_deployment_result(result: DeploymentResult) -> dict[str, Any]:
    """Serialize deployment result into structured changes.

    Args:
        result: The deployment result to serialize.

    Returns:
        Serialized changes representing the deployment result.
    """
    result_dict = {"unique_id": uuid.uuid4().hex[:8], "status": result.status, "is_dry_run": result.is_dry_run}

    stats = DeploymentStatistics.from_deployment_result(result)
    changes = SerializedChanges.from_deployment_result(result)

    result_dict["total_changes"] = stats.total_changes
    result_dict["created"] = stats.by_change_type.create
    result_dict["updated"] = stats.by_change_type.update
    result_dict["deleted"] = stats.by_change_type.delete
    result_dict["skipped"] = stats.by_change_type.skip
    result_dict["unchanged"] = stats.by_change_type.unchanged
    result_dict["failed"] = stats.by_change_type.failed

    result_dict["STATS_JSON"] = stats.model_dump_json()
    result_dict["CHANGES_JSON"] = changes.model_dump_json_flat()

    return result_dict
