"""Helper functions for creating fix actions on DMS schemas."""

import hashlib
from collections.abc import Callable

from cognite.neat._data_model.models.dms._constraints import RequiresConstraintDefinition
from cognite.neat._data_model.models.dms._references import ContainerReference
from cognite.neat._data_model.models.dms._schema import RequestSchema

# CDF constraint identifier max length is 43 characters
MAX_CONSTRAINT_ID_LENGTH = 43
AUTO_SUFFIX = "__auto"
HASH_LENGTH = 8  # Short hash to ensure uniqueness when truncating
# When truncating: base_id + "_" + hash + suffix
# e.g., "VeryLongContainerName_a1b2c3d4__auto" (max 43 chars)
MAX_BASE_ID_LENGTH_WITH_HASH = MAX_CONSTRAINT_ID_LENGTH - len(AUTO_SUFFIX) - HASH_LENGTH - 1  # 28 characters
MAX_BASE_ID_LENGTH_NO_HASH = MAX_CONSTRAINT_ID_LENGTH - len(AUTO_SUFFIX)  # 37 characters


def make_auto_constraint_id(dst: ContainerReference) -> str:
    """Generate a constraint identifier for auto-generated requires constraints.

    CDF has a 43-character limit on constraint identifiers. This function
    ensures the ID stays within that limit while maintaining uniqueness.

    For short external_ids (≤37 chars): uses "{external_id}__auto"
    For long external_ids (>37 chars): uses "{truncated_id}_{hash}__auto"
        where hash is 8 chars derived from the full external_id
    """
    base_id = dst.external_id

    if len(base_id) <= MAX_BASE_ID_LENGTH_NO_HASH:
        # No truncation needed
        return f"{base_id}{AUTO_SUFFIX}"

    # Truncation needed - include hash for uniqueness
    hash_input = f"{dst.space}:{dst.external_id}"
    hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[:HASH_LENGTH]
    truncated_id = base_id[:MAX_BASE_ID_LENGTH_WITH_HASH]
    return f"{truncated_id}_{hash_suffix}{AUTO_SUFFIX}"


def make_add_constraint_fn(src: ContainerReference, dst: ContainerReference) -> Callable[[RequestSchema], None]:
    """Create a closure that adds a requires constraint from src to dst."""

    def apply(schema: RequestSchema) -> None:
        for container in schema.containers:
            if container.as_reference() == src:
                constraint_id = make_auto_constraint_id(dst)
                if container.constraints is None:
                    container.constraints = {}
                container.constraints[constraint_id] = RequiresConstraintDefinition(require=dst)
                break

    return apply


def make_remove_constraint_fn(
    src: ContainerReference, dst: ContainerReference, *, auto_only: bool = True
) -> Callable[[RequestSchema], None]:
    """Create a closure that removes a requires constraint from src to dst.

    Args:
        src: Source container reference.
        dst: Destination container reference (the required container).
        auto_only: If True (default), only removes constraints with '__auto' suffix
            (auto-generated constraints). If False, removes ALL matching constraints
            regardless of their ID. Use False for cycle breaking where user-defined
            constraints may also need removal.
    """

    def apply(schema: RequestSchema) -> None:
        for container in schema.containers:
            if container.as_reference() == src and container.constraints:
                to_remove: list[str] = []
                for constraint_id, constraint in container.constraints.items():
                    if isinstance(constraint, RequiresConstraintDefinition) and constraint.require == dst:
                        if not auto_only or constraint_id.endswith(AUTO_SUFFIX):
                            to_remove.append(constraint_id)
                for constraint_id in to_remove:
                    del container.constraints[constraint_id]
                # Clean up empty constraints dict
                if not container.constraints:
                    container.constraints = None
                break

    return apply
