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
class FailedRequest:
    error_message: str
    status_code: int
    resource_ids: list[Hashable] = field(default_factory=list)


@dataclass
class ForcedResource:
    resource_id: Hashable
    reason: str


@dataclass
class DeployResult:
    # Deployment status
    status: Literal["success", "failure", "dry-run"] = "success"
    restored: bool = False
    message: str = ""

    # Preparation phase
    diffs: list[ResourceDifference] = field(default_factory=list)
    to_create: list[Hashable] = field(default_factory=list)
    to_update: list[Hashable] = field(default_factory=list)
    to_delete: list[Hashable] = field(default_factory=list)

    # No API calls are made when existing is set to "skip", "fail", or "recreate"
    skipped: list[Hashable] = field(default_factory=list)
    unchanged: list[Hashable] = field(default_factory=list)
    existing: list[Hashable] = field(default_factory=list)

    # Result phase
    created: list[Hashable] = field(default_factory=list)
    failed_created: list[FailedRequest] = field(default_factory=list)
    deleted: list[Hashable] = field(default_factory=list)
    failed_deleted: list[FailedRequest] = field(default_factory=list)

    updated: list[ResourceDifference] = field(default_factory=list)
    failed_updated: list[FailedRequest] = field(default_factory=list)
    forced: list[ForcedResource] = field(default_factory=list)

    failed_restored: list[FailedRequest] = field(default_factory=list)
