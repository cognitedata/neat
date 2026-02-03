"""Helper functions for creating fix actions on DMS schemas."""

import hashlib
from dataclasses import dataclass

from cognite.neat._data_model.models.dms._constraints import RequiresConstraintDefinition
from cognite.neat._data_model.models.dms._container import ContainerRequest
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


@dataclass
class AddConstraintAction:
    """Callable that adds a requires constraint from src to dst container."""

    src: ContainerReference
    dst: ContainerReference

    def __call__(self, schema: RequestSchema) -> None:
        for container in schema.containers:
            if container.as_reference() == self.src:
                constraint_id = make_auto_constraint_id(self.dst)
                if container.constraints is None:
                    container.constraints = {}
                container.constraints[constraint_id] = RequiresConstraintDefinition(require=self.dst)
                break


@dataclass
class RemoveConstraintAction:
    """Callable that removes a requires constraint from src to dst container.

    Attributes:
        src: Source container reference.
        dst: Destination container reference (the required container).
        auto_only: If True (default), only removes constraints with '__auto' suffix
            (auto-generated constraints). If False, removes ALL matching constraints
            regardless of their ID. Use False for cycle breaking where user-defined
            constraints may also need removal.
    """

    src: ContainerReference
    dst: ContainerReference
    auto_only: bool = True

    def __call__(self, schema: RequestSchema) -> None:
        for container in schema.containers:
            if container.as_reference() == self.src and container.constraints:
                to_remove: list[str] = []
                for constraint_id, constraint in container.constraints.items():
                    if isinstance(constraint, RequiresConstraintDefinition) and constraint.require == self.dst:
                        if not self.auto_only or constraint_id.endswith(AUTO_SUFFIX):
                            to_remove.append(constraint_id)
                for constraint_id in to_remove:
                    del container.constraints[constraint_id]
                # Clean up empty constraints dict
                if not container.constraints:
                    container.constraints = None
                break


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
