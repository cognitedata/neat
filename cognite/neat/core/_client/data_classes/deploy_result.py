from collections.abc import Hashable
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Property:
    location: str
    value_representation: str


@dataclass
class PropertyChange(Property):
    previous_representation: str


@dataclass
class ResourceDifference:
    resource_id: Hashable
    added: list[Property] = field(default_factory=list)
    removed: list[Property] = field(default_factory=list)
    changed: list[PropertyChange] = field(default_factory=list)

    def __bool__(self) -> bool:
        """Check if there are any differences."""
        return bool(self.added or self.removed or self.changed)


@dataclass
class DeployResult:
    status: Literal["success", "failure", "dry-run"]

    diffs: list[ResourceDifference] = field(default_factory=list)
    to_create: list[Hashable] = field(default_factory=list)
    to_update: list[Hashable] = field(default_factory=list)
    to_delete: list[Hashable] = field(default_factory=list)

    created: list[Hashable] = field(default_factory=list)
    deleted: list[Hashable] = field(default_factory=list)
    skipped: list[Hashable] = field(default_factory=list)
    unchanged: list[Hashable] = field(default_factory=list)
    existing: list[Hashable] = field(default_factory=list)
    updated: list[ResourceDifference] = field(default_factory=list)
