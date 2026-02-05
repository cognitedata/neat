import hashlib

from cognite.neat._data_model.models.dms._references import ContainerReference

# CDF constraint and index identifier max length is 43 characters
MAX_IDENTIFIER_LENGTH = 43
AUTO_SUFFIX = "__auto"
HASH_LENGTH = 8  # Short hash to ensure uniqueness when truncating
# When truncating: base_id + "_" + hash + suffix
# e.g., "VeryLongContainerName_a1b2c3d4__auto" (max 43 chars)
MAX_BASE_LENGTH_NO_HASH = MAX_IDENTIFIER_LENGTH - len(AUTO_SUFFIX)  # 37 characters
MAX_BASE_LENGTH_WITH_HASH = MAX_BASE_LENGTH_NO_HASH - HASH_LENGTH - 1  # 28 characters


def make_auto_id(base_id: str) -> str:
    """Generate an auto-generated identifier with truncation if needed.

    CDF has a 43-character limit on constraint/index identifiers. This function
    ensures the ID stays within that limit while maintaining uniqueness.

    Args:
        base_id: The primary identifier to use (e.g., external_id or property_id).

    Returns:
        For short base_ids (≤37 chars): "{base_id}__auto"
        For long base_ids (>37 chars): "{truncated_id}_{hash}__auto"
    """
    if len(base_id) <= MAX_BASE_LENGTH_NO_HASH:
        return f"{base_id}{AUTO_SUFFIX}"

    hash_suffix = hashlib.sha256(base_id.encode()).hexdigest()[:HASH_LENGTH]
    truncated_id = base_id[:MAX_BASE_LENGTH_WITH_HASH]
    return f"{truncated_id}_{hash_suffix}{AUTO_SUFFIX}"


def make_auto_constraint_id(dst: ContainerReference) -> str:
    """Generate a constraint identifier for auto-generated requires constraints."""
    return make_auto_id(dst.external_id)


def make_auto_index_id(property_id: str) -> str:
    """Generate an index identifier for auto-generated indexes."""
    return make_auto_id(property_id)
