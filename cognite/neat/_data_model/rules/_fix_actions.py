"""Fix actions for auto-fixing data model issues."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from cognite.neat._data_model.models.dms._references import ContainerReference, ViewReference
    from cognite.neat._data_model.models.dms._schema import RequestSchema


@dataclass
class FixAction:
    """An atomic, individually-applicable fix for a schema issue.

    Each FixAction represents a single change that can be applied to a RequestSchema
    to fix an issue identified by a validator. Fix actions are designed to be:
    - Atomic: Each action makes exactly one change
    - Identifiable: Has a unique fix_id for opt-in/opt-out filtering
    - Orderable: Has a priority for determining application order
    - Targetable: Specifies which resource is being modified

    Attributes:
        fix_id: Unique identifier for this fix action. Used for filtering and deduplication.
            Convention: "{validator_code}:{action}:{target}" e.g., "NEAT-DMS-PERFORMANCE-001:add:space:A->space:B"
        description: Human-readable description of what this fix does (specific action).
        message: Generic description of the fix category (shown in the info box).
        target_type: The type of resource being modified ("container", "view", or "data_model").
        target_ref: Reference to the specific resource being modified.
        apply: Callable that applies the fix to a RequestSchema in-place.
        priority: Order in which fixes should be applied. Lower values = applied first.
            Default priorities:
            - 30: Cycle breaking (must happen first)
            - 40: Constraint removal
            - 50: Constraint addition
        depends_on: Optional list of fix_ids that must be applied before this one.
    """

    fix_id: str
    description: str
    message: str
    target_type: Literal["container", "view", "data_model"]
    target_ref: "ContainerReference | ViewReference"
    apply: Callable[["RequestSchema"], None]
    priority: int = 100
    depends_on: Sequence[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.fix_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FixAction):
            return NotImplemented
        return self.fix_id == other.fix_id
