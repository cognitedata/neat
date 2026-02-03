"""Fix actions for auto-fixing data model issues."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from cognite.neat._data_model._fix_helpers import AUTO_SUFFIX, make_auto_constraint_id, make_auto_index_id
from cognite.neat._data_model.models.dms._constraints import RequiresConstraintDefinition
from cognite.neat._data_model.models.dms._indexes import BtreeIndex
from cognite.neat._data_model.models.dms._references import ContainerReference
from cognite.neat._data_model.models.dms._schema import RequestSchema


@dataclass
class FixAction(ABC):
    """An atomic, individually-applicable fix for a schema issue.

    Each FixAction represents a single change that can be applied to a RequestSchema
    to fix an issue identified by a validator. Fix actions are designed to be:
    - Atomic: Each action makes exactly one change
    - Identifiable: Has a unique fix_id for opt-in/opt-out filtering

    Attributes:
        fix_id: Unique identifier for this fix action. Used for filtering and deduplication.
            Convention: "{validator_code}:{action}:{target}" e.g., "NEAT-DMS-PERFORMANCE-001:add:space:A->space:B"
        message: Human-readable description of what this fix does.
        code: The validator code (e.g., "NEAT-DMS-PERFORMANCE-001") for grouping in UI.
    """

    fix_id: str
    message: str
    code: str

    @abstractmethod
    def __call__(self, schema: RequestSchema) -> None:
        """Apply this fix to the schema in-place."""
        ...

    def __hash__(self) -> int:
        return hash(self.fix_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FixAction):
            return NotImplemented
        return self.fix_id == other.fix_id


@dataclass(eq=False)
class AddConstraintAction(FixAction):
    """Fix action that adds a requires constraint from source to dest container."""

    source: ContainerReference
    dest: ContainerReference

    @property
    def source_name(self) -> str:
        return self.source.external_id

    @property
    def dest_name(self) -> str:
        return self.dest.external_id

    @property
    def action_type(self) -> Literal["add"]:
        return "add"

    @property
    def constraint_id(self) -> str:
        return make_auto_constraint_id(self.dest)

    def __call__(self, schema: RequestSchema) -> None:
        for container in schema.containers:
            if container.as_reference() == self.source:
                constraint_id = make_auto_constraint_id(self.dest)
                if container.constraints is None:
                    container.constraints = {}
                container.constraints[constraint_id] = RequiresConstraintDefinition(require=self.dest)
                break


@dataclass(eq=False)
class RemoveConstraintAction(FixAction):
    """Fix action that removes a requires constraint from source to dest container.

    Attributes:
        source: Source container reference.
        dest: Destination container reference (the required container).
        auto_only: If True (default), only removes constraints with '__auto' suffix
            (auto-generated constraints). If False, removes ALL matching constraints
            regardless of their ID. Use False for cycle breaking where user-defined
            constraints may also need removal.
    """

    source: ContainerReference
    dest: ContainerReference
    auto_only: bool = True

    @property
    def source_name(self) -> str:
        return self.source.external_id

    @property
    def dest_name(self) -> str:
        return self.dest.external_id

    @property
    def action_type(self) -> Literal["remove"]:
        return "remove"

    @property
    def constraint_id(self) -> str | None:
        # Note: This returns the auto-generated ID. To find an existing constraint ID,
        # you would need access to the schema via find_requires_constraint_id.
        return make_auto_constraint_id(self.dest)

    def __call__(self, schema: RequestSchema) -> None:
        for container in schema.containers:
            if container.as_reference() == self.source and container.constraints:
                to_remove: list[str] = []
                for constraint_id, constraint in container.constraints.items():
                    if isinstance(constraint, RequiresConstraintDefinition) and constraint.require == self.dest:
                        if not self.auto_only or constraint_id.endswith(AUTO_SUFFIX):
                            to_remove.append(constraint_id)
                for constraint_id in to_remove:
                    del container.constraints[constraint_id]
                # Clean up empty constraints dict
                if not container.constraints:
                    container.constraints = None
                break


@dataclass(eq=False)
class AddIndexAction(FixAction):
    """Fix action that adds a cursorable B-tree index to a container property."""

    container: ContainerReference
    property_id: str

    @property
    def container_name(self) -> str:
        return self.container.external_id

    @property
    def index_id(self) -> str:
        return make_auto_index_id(self.container, self.property_id)

    def __call__(self, schema: RequestSchema) -> None:
        for container in schema.containers:
            if container.as_reference() == self.container:
                index_id = make_auto_index_id(self.container, self.property_id)
                if container.indexes is None:
                    container.indexes = {}
                container.indexes[index_id] = BtreeIndex(properties=[self.property_id], cursorable=True)
                break
