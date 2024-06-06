from abc import ABC
from dataclasses import dataclass, field
from functools import total_ordering

from cognite.neat.issues import NeatIssueList


@total_ordering
@dataclass
class UploadResultCore(ABC):
    name: str
    error_messages: list[str] = field(default_factory=list)
    issues: NeatIssueList = field(default_factory=NeatIssueList)

    def __lt__(self, other: object) -> bool:
        if isinstance(other, UploadDiffsCount):
            return self.name < other.name
        else:
            return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, UploadDiffsCount):
            return self.name == other.name
        else:
            return NotImplemented


@dataclass
class UploadDiffsCount(UploadResultCore):
    created: int = 0
    deleted: int = 0
    changed: int = 0
    unchanged: int = 0
    skipped: int = 0
    failed_created: int = 0
    failed_changed: int = 0
    failed_deleted: int = 0

    @property
    def total(self) -> int:
        return self.created + self.deleted + self.changed + self.unchanged

    @property
    def failed(self) -> int:
        return self.failed_created + self.failed_changed + self.failed_deleted

    def as_report_str(self) -> str:
        line = []
        if self.created:
            line.append(f"created {self.created}")
        if self.changed:
            line.append(f"updated {self.changed}")
        if self.skipped:
            line.append(f"skipped {self.skipped}")
        if self.unchanged:
            line.append(f"unchanged {self.unchanged}")
        if self.deleted:
            line.append(f"deleted {self.deleted}")
        if self.failed_created:
            line.append(f"failed to create {self.failed_created}")
        if self.failed_changed:
            line.append(f"failed to update {self.failed_changed}")
        if self.failed_deleted:
            line.append(f"failed to delete {self.failed_deleted}")

        return f"{self.name.title()}: {', '.join(line)}"


@dataclass
class UploadResultIDs(UploadResultCore):
    success: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


@dataclass
class UploadDiffsID(UploadResultCore):
    created: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def as_upload_result_ids(self) -> UploadResultIDs:
        result = UploadResultIDs(name=self.name, error_messages=self.error_messages, issues=self.issues)
        result.success = self.created + self.changed + self.unchanged
        result.failed = self.failed
        return result
