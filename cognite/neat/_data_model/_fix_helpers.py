"""Helper functions for creating fix actions on DMS schemas."""

import hashlib

from cognite.neat._data_model.models.dms._constraints import RequiresConstraintDefinition
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._references import ContainerReference

# CDF constraint and index identifier max length is 43 characters
MAX_IDENTIFIER_LENGTH = 43
AUTO_SUFFIX = "__auto"
HASH_LENGTH = 8  # Short hash to ensure uniqueness when truncating
# When truncating: base_id + "_" + hash + suffix
# e.g., "VeryLongContainerName_a1b2c3d4__auto" (max 43 chars)
MAX_BASE_LENGTH_WITH_HASH = MAX_IDENTIFIER_LENGTH - len(AUTO_SUFFIX) - HASH_LENGTH - 1  # 28 characters
MAX_BASE_LENGTH_NO_HASH = MAX_IDENTIFIER_LENGTH - len(AUTO_SUFFIX)  # 37 characters


def make_auto_constraint_id(dst: ContainerReference) -> str:
    """Generate a constraint identifier for auto-generated requires constraints.

    CDF has a 43-character limit on constraint identifiers. This function
    ensures the ID stays within that limit while maintaining uniqueness.

    For short external_ids (≤37 chars): uses "{external_id}__auto"
    For long external_ids (>37 chars): uses "{truncated_id}_{hash}__auto"
        where hash is 8 chars derived from the full external_id
    """
    base_id = dst.external_id

    if len(base_id) <= MAX_BASE_LENGTH_NO_HASH:
        # No truncation needed
        return f"{base_id}{AUTO_SUFFIX}"

    # Truncation needed - include hash for uniqueness
    hash_input = f"{dst.space}:{dst.external_id}"
    hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[:HASH_LENGTH]
    truncated_id = base_id[:MAX_BASE_LENGTH_WITH_HASH]
    return f"{truncated_id}_{hash_suffix}{AUTO_SUFFIX}"


def find_requires_constraint_id(
    src: ContainerReference,
    dst: ContainerReference,
    containers: dict[ContainerReference, ContainerRequest],
) -> str | None:
    """Find the constraint ID for a requires constraint from src to dst.

    Args:
        src: Source container reference.
        dst: Destination container reference (the required container).
        containers: Dict mapping container references to their definitions.

    Returns:
        The constraint ID if found, None otherwise.
    """
    container = containers.get(src)
    if container and container.constraints:
        for constraint_id, constraint in container.constraints.items():
            if isinstance(constraint, RequiresConstraintDefinition) and constraint.require == dst:
                return constraint_id
    return None


def find_requires_constraints(
    src: ContainerReference,
    dst: ContainerReference,
    containers: dict[ContainerReference, ContainerRequest],
    auto_only: bool = True,
) -> list[tuple[str, RequiresConstraintDefinition]]:
    """Find all requires constraints from src to dst.

    Args:
        src: Source container reference.
        dst: Destination container reference (the required container).
        containers: Dict mapping container references to their definitions.
        auto_only: If True, only return auto-generated constraints (ending with __auto).
            If False, return all matching constraints.

    Returns:
        List of (constraint_id, constraint_definition) tuples.
    """
    result: list[tuple[str, RequiresConstraintDefinition]] = []
    container = containers.get(src)
    if container and container.constraints:
        for constraint_id, constraint in container.constraints.items():
            if isinstance(constraint, RequiresConstraintDefinition) and constraint.require == dst:
                if not auto_only or constraint_id.endswith(AUTO_SUFFIX):
                    result.append((constraint_id, constraint))
    return result


def make_auto_index_id(container_ref: ContainerReference, property_id: str) -> str:
    """Generate an index identifier for auto-generated indexes.

    CDF has a 43-character limit on index identifiers. This function
    ensures the ID stays within that limit while maintaining uniqueness.

    For short property_ids (≤37 chars): uses "{property_id}__auto"
    For long property_ids (>37 chars): uses "{truncated_id}_{hash}__auto"
        where hash is 8 chars derived from container+property
    """
    if len(property_id) <= MAX_BASE_LENGTH_NO_HASH:
        return f"{property_id}{AUTO_SUFFIX}"

    hash_input = f"{container_ref.space}:{container_ref.external_id}:{property_id}"
    hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[:HASH_LENGTH]
    truncated_id = property_id[:MAX_BASE_LENGTH_WITH_HASH]
    return f"{truncated_id}_{hash_suffix}{AUTO_SUFFIX}"
