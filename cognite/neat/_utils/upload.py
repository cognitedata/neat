from abc import ABC
from dataclasses import dataclass, field
from functools import total_ordering
from typing import Any, Generic

from cognite.neat._issues import NeatIssueList
from cognite.neat._shared import T_ID, NeatList, NeatObject


@total_ordering
@dataclass
class UploadResultCore(NeatObject, ABC):
    name: str
    error_messages: list[str] = field(default_factory=list)
    issues: NeatIssueList = field(default_factory=NeatIssueList)

    def __lt__(self, other: object) -> bool:
        if isinstance(other, UploadResultCore):
            return self.name < other.name
        else:
            return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, UploadResultCore):
            return self.name == other.name
        else:
            return NotImplemented

    def dump(self, aggregate: bool = True) -> dict[str, Any]:
        return {"name": self.name}


class UploadResultList(NeatList[UploadResultCore]): ...


@dataclass
class UploadResult(UploadResultCore, Generic[T_ID]):
    created: set[T_ID] = field(default_factory=set)
    upserted: set[T_ID] = field(default_factory=set)
    deleted: set[T_ID] = field(default_factory=set)
    changed: set[T_ID] = field(default_factory=set)
    unchanged: set[T_ID] = field(default_factory=set)
    skipped: set[T_ID] = field(default_factory=set)
    failed_created: set[T_ID] = field(default_factory=set)
    failed_upserted: set[T_ID] = field(default_factory=set)
    failed_changed: set[T_ID] = field(default_factory=set)
    failed_deleted: set[T_ID] = field(default_factory=set)

    @property
    def failed(self) -> int:
        return (
            len(self.failed_created) + len(self.failed_changed) + len(self.failed_deleted) + len(self.failed_upserted)
        )

    @property
    def success(self) -> int:
        return (
            len(self.created)
            + len(self.deleted)
            + len(self.changed)
            + len(self.upserted)
            + len(self.unchanged)
            + len(self.skipped)
        )

    def dump(self, aggregate: bool = True) -> dict[str, Any]:
        output = super().dump(aggregate)
        if self.created:
            output["created"] = len(self.created) if aggregate else list(self.created)
        if self.upserted:
            output["upserted"] = len(self.upserted) if aggregate else list(self.upserted)
        if self.deleted:
            output["deleted"] = len(self.deleted) if aggregate else list(self.deleted)
        if self.changed:
            output["changed"] = len(self.changed) if aggregate else list(self.changed)
        if self.unchanged:
            output["unchanged"] = len(self.unchanged) if aggregate else list(self.unchanged)
        if self.skipped:
            output["skipped"] = len(self.skipped) if aggregate else list(self.skipped)
        if self.failed_created:
            output["failed_created"] = len(self.failed_created) if aggregate else list(self.failed_created)
        if self.failed_upserted:
            output["failed_upserted"] = len(self.failed_upserted) if aggregate else list(self.failed_upserted)
        if self.failed_changed:
            output["failed_changed"] = len(self.failed_changed) if aggregate else list(self.failed_changed)
        if self.failed_deleted:
            output["failed_deleted"] = len(self.failed_deleted) if aggregate else list(self.failed_deleted)
        if self.error_messages:
            output["error_messages"] = len(self.error_messages) if aggregate else self.error_messages
        if self.issues:
            output["issues"] = len(self.issues) if aggregate else [issue.dump() for issue in self.issues]
        return output

    def __str__(self) -> str:
        dumped = self.dump(aggregate=True)
        lines: list[str] = []
        for key, value in dumped.items():
            if key in ["name", "error_messages", "issues"]:
                continue
            lines.append(f"{key}: {value}")
        return f"{self.name.title()}: {', '.join(lines)}"
